"""Unified native WebSocket endpoint (SOCKET_EVENTS.md §2–3)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.deps import get_session_factory
from app.api.websocket.auth import authenticate_websocket
from app.api.websocket.connection_manager import WSConnection, connection_manager
from app.api.websocket.dispatcher import (
    EventDispatcher,
    build_participant_snapshot,
    build_room_snapshot,
    notify_participant_presence,
)
from app.api.websocket.events import ClientRole, ServerEventType
from app.api.websocket.heartbeat import HEARTBEAT_INTERVAL_SECONDS
from app.config import get_settings
from app.core.exceptions import QuizArenaError
from app.models.enums import ConnectionStatus, ParticipantState
from app.models.participant import Participant
from app.schemas.websocket import (
    ConnectionAckPayload,
    ResyncPayload,
    make_error,
)
from app.services.quiz_execution_service import QuizExecutionService
from app.services.response_service import ResponseService

logger = logging.getLogger(__name__)

router = APIRouter()

# Close codes
_CLOSE_POLICY = 1008
_CLOSE_REPLACED = 4000


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Unified WebSocket entry.

    Query params:
      - role: admin | participant | display
      - token: JWT | participant session token | presentation secretToken
      - roomId: required for admin
      - protocolVersion: optional (default 1.0)
    """
    await websocket.accept()

    role = websocket.query_params.get("role")
    token = websocket.query_params.get("token")
    room_id = websocket.query_params.get("roomId")
    protocol_version = websocket.query_params.get("protocolVersion") or "1.0"

    session_factory = get_session_factory()
    session: Session = session_factory()
    connection: WSConnection | None = None

    try:
        settings = get_settings()
        try:
            auth = authenticate_websocket(
                session=session,
                settings=settings,
                role=role,
                token=token,
                room_id=room_id,
            )
        except QuizArenaError as exc:
            await websocket.send_json(make_error(exc.code, exc.message, details=exc.details))
            await websocket.close(code=_CLOSE_POLICY, reason=exc.code)
            return

        connection = WSConnection(
            websocket=websocket,
            role=auth.role,
            room_id=auth.room.id,
            participant_id=auth.participant.id if auth.participant else None,
            auth_token=token if auth.role == ClientRole.ADMIN else None,
        )
        replaced = await connection_manager.connect(connection)
        if replaced is not None:
            await connection_manager.close_connection(
                replaced,
                code=_CLOSE_REPLACED,
                reason="Replaced by newer connection",
            )

        await _send_handshake(
            connection,
            auth.room,
            auth.participant,
            protocol_version,
            session=session,
        )

        if auth.role == ClientRole.PARTICIPANT and auth.participant is not None:
            presence_event = (
                ServerEventType.PARTICIPANT_RECONNECTED
                if auth.is_reconnect
                else ServerEventType.PARTICIPANT_JOINED
            )
            await notify_participant_presence(
                connection_manager,
                room_id=auth.room.id,
                event_type=presence_event,
                participant=auth.participant,
                session=session,
            )

        dispatcher = EventDispatcher(connection_manager, session)
        while True:
            raw = await websocket.receive_json()
            if not isinstance(raw, dict):
                await connection_manager.send_to_connection(
                    connection,
                    ServerEventType.ERROR,
                    make_error("VALIDATION_ERROR", "JSON object required")["payload"],
                )
                continue
            await dispatcher.dispatch(connection, raw)

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected")
    except Exception:
        logger.exception("WebSocket handler error")
        if connection is not None:
            try:
                await connection_manager.send_to_connection(
                    connection,
                    ServerEventType.ERROR,
                    make_error("INTERNAL_ERROR", "Unexpected WebSocket failure")["payload"],
                )
            except Exception:
                pass
    finally:
        if connection is not None:
            await _cleanup_connection(session, connection)
        session.close()


async def _send_handshake(
    connection: WSConnection,
    room,
    participant,
    protocol_version: str,
    *,
    session: Session,
) -> None:
    ack = ConnectionAckPayload(
        connection_id=connection.connection_id,
        role=connection.role.value,
        room_id=connection.room_id,
        protocol_version=protocol_version,
        heartbeat_interval_seconds=int(HEARTBEAT_INTERVAL_SECONDS),
    )
    await connection_manager.send_to_connection(
        connection,
        ServerEventType.CONNECTION_ACK,
        ack.model_dump(mode="json", by_alias=True),
    )

    submission: dict | None = None
    question_snapshot: dict | None = None
    leaderboard: list | None = None
    podium: dict | None = None
    participant_count: int | None = None
    timer_payload: dict | None = None

    from app.api.websocket.dispatcher import count_active_participants
    from app.models.enums import RoomState
    from app.services.leaderboard_service import LeaderboardService

    participant_count = count_active_participants(session, room.id)

    # Shared live snapshot for admin, display, and participant reconnects.
    execution = QuizExecutionService(session).get_execution_state(room.id)
    if execution.question is not None and room.state not in {
        RoomState.COMPLETED,
        RoomState.CLOSED,
    }:
        reveal = execution.question.state.value in {"Revealed", "Scored"}
        question_snapshot = QuizExecutionService(session)._question_payload(
            room,
            execution.question,
            execution.question.session_section,
            include_correct=reveal,
        )
        question_snapshot["isAcceptingAnswers"] = execution.is_accepting_answers
        question_snapshot["questionIndex"] = execution.question_index
        # Prefer pause-aware ends from _question_payload (do not overwrite).
        ends_at = question_snapshot.get("timerEndsAt")
        nested_q = question_snapshot.get("question")
        if not ends_at and isinstance(nested_q, dict):
            ends_at = nested_q.get("timerEndsAt")
        if ends_at:
            timer_payload = {
                "endsAt": ends_at,
                "timeLimitSeconds": execution.question.time_limit_seconds,
                "timerPaused": bool(
                    (nested_q or {}).get("timerPaused")
                    if isinstance(nested_q, dict)
                    else False
                ),
            }

    board = LeaderboardService(session).snapshot(room.id)
    leaderboard = board.get("entries")
    podium = board.get("podium") if room.state in {RoomState.COMPLETED, RoomState.CLOSED} else None
    session.commit()

    if connection.role == ClientRole.PARTICIPANT and participant is not None:
        responses = ResponseService(session)
        submission = responses.get_submission_status(
            room_id=room.id,
            participant_id=participant.id,
        )

    resync = ResyncPayload(
        role=connection.role.value,
        room=build_room_snapshot(room),
        participant=(
            build_participant_snapshot(participant, submission=submission)
            if participant
            else None
        ),
        question=question_snapshot,
        submission=submission,
        leaderboard=leaderboard,
        podium=podium,
        participant_count=participant_count,
        timer=timer_payload,
    )
    await connection_manager.send_to_connection(
        connection,
        ServerEventType.RESYNC,
        resync.model_dump(mode="json", by_alias=True, exclude_none=False),
    )


async def _cleanup_connection(session: Session, connection: WSConnection) -> None:
    await connection_manager.disconnect(connection)

    if connection.role != ClientRole.PARTICIPANT or connection.participant_id is None:
        return

    participant = session.get(Participant, connection.participant_id)
    if participant is None:
        return

    # Only mark disconnected if this socket still "owns" presence
    # (a newer reconnect may have already replaced us).
    pool = connection_manager.get_room_pool(connection.room_id)
    if pool is not None and connection.participant_id in pool.participants:
        return

    participant.state = ParticipantState.DISCONNECTED
    participant.connection_status = ConnectionStatus.DISCONNECTED
    try:
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to persist participant disconnect")
        return

    # Presence: socket drop is a disconnect, not an explicit leave.
    # Emitting participant:left here made hosts treat brief StrictMode /
    # reconnect blips as permanent departures and confused lobby counts.
    await notify_participant_presence(
        connection_manager,
        room_id=connection.room_id,
        event_type=ServerEventType.PARTICIPANT_DISCONNECTED,
        participant=participant,
        session=session,
    )
