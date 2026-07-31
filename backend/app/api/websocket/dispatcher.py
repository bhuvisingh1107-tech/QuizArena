"""Client event routing (SOCKET_EVENTS.md §8)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.api.websocket.connection_manager import ConnectionManager, WSConnection
from app.api.websocket.events import (
    DEFERRED_CLIENT_EVENTS,
    EXECUTION_CLIENT_EVENTS,
    ClientEventType,
    ClientRole,
    ServerEventType,
)
from app.core.exceptions import QuizArenaError
from app.models.enums import RoomState
from app.schemas.websocket import make_error
from app.services.live_room_service import LiveRoomService
from app.services.quiz_execution_service import QuizExecutionService
from app.services.response_service import ResponseService

logger = logging.getLogger(__name__)


class EventDispatcher:
    """Validate and route client WebSocket events to existing services."""

    def __init__(
        self,
        manager: ConnectionManager,
        session: Session,
    ) -> None:
        self._manager = manager
        self._session = session
        self._rooms = LiveRoomService(session)
        self._execution = QuizExecutionService(session)
        self._responses = ResponseService(session)

    async def dispatch(self, connection: WSConnection, raw: dict[str, Any]) -> None:
        event_type = raw.get("type")
        if not isinstance(event_type, str) or not event_type:
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ERROR,
                make_error("VALIDATION_ERROR", "Message 'type' is required")["payload"],
            )
            return

        payload = raw.get("payload") or {}
        if not isinstance(payload, dict):
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ERROR,
                make_error("VALIDATION_ERROR", "Message 'payload' must be an object")["payload"],
            )
            return

        if event_type == ClientEventType.PING:
            await self._manager.send_to_connection(
                connection,
                ServerEventType.PONG,
                {"echo": payload},
            )
            return

        if event_type == ClientEventType.PONG:
            import time

            connection.last_pong_at = time.monotonic()
            return

        if connection.role == ClientRole.DISPLAY:
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ERROR,
                make_error(
                    "FORBIDDEN",
                    "Presentation display is receive-only and cannot send control events",
                )["payload"],
            )
            return

        if event_type in DEFERRED_CLIENT_EVENTS:
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ERROR,
                make_error(
                    "BUSINESS_RULE",
                    f"Event '{event_type}' is not available yet",
                )["payload"],
            )
            return

        if connection.role == ClientRole.ADMIN:
            if event_type in EXECUTION_CLIENT_EVENTS:
                await self._dispatch_execution(connection, event_type)
                return
            await self._dispatch_admin(connection, event_type)
            return

        if connection.role == ClientRole.PARTICIPANT:
            if event_type == ClientEventType.PARTICIPANT_SUBMIT:
                await self._dispatch_answer_submit(connection, payload)
                return
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ERROR,
                make_error(
                    "FORBIDDEN",
                    f"Participant event '{event_type}' is not supported",
                )["payload"],
            )
            return

    async def _dispatch_admin(self, connection: WSConnection, event_type: str) -> None:
        action_map = {
            ClientEventType.ADMIN_OPEN_LOBBY: ("open_lobby", ServerEventType.ROOM_LOBBY_OPENED),
            ClientEventType.ADMIN_TOGGLE_LOBBY: ("toggle_lobby", ServerEventType.ROOM_STATE_CHANGED),
            ClientEventType.ADMIN_START: ("start", ServerEventType.ROOM_SESSION_STARTED),
            ClientEventType.ADMIN_PAUSE: ("pause", ServerEventType.ROOM_PAUSED),
            ClientEventType.ADMIN_RESUME: ("resume", ServerEventType.ROOM_RESUMED),
            ClientEventType.ADMIN_END: ("end", ServerEventType.ROOM_COMPLETED),
            ClientEventType.ADMIN_CLOSE: ("close", ServerEventType.ROOM_CLOSED),
        }
        mapped = action_map.get(event_type)  # type: ignore[arg-type]
        if mapped is None:
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ERROR,
                make_error("VALIDATION_ERROR", f"Unknown admin event '{event_type}'")["payload"],
            )
            return

        method_name, broadcast_type = mapped
        try:
            method = getattr(self._rooms, method_name)
            room = method(connection.room_id)
        except QuizArenaError as exc:
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ERROR,
                make_error(exc.code, exc.message, details=exc.details)["payload"],
            )
            return

        room_payload = {
            "roomId": str(room.id),
            "state": room.state.value,
            "lobbySubState": room.lobby_sub_state.value if room.lobby_sub_state else None,
            "codesExpired": room.codes_expired,
        }
        await self._manager.broadcast_to_room(
            connection.room_id,
            broadcast_type,
            room_payload,
        )
        await self._manager.broadcast_to_room(
            connection.room_id,
            ServerEventType.ROOM_STATE_CHANGED,
            room_payload,
        )

    async def _dispatch_execution(self, connection: WSConnection, event_type: str) -> None:
        try:
            if event_type == ClientEventType.ADMIN_START_QUESTION:
                result = self._execution.start_first_question(connection.room_id)
            elif event_type == ClientEventType.ADMIN_CLOSE_QUESTION:
                result = self._execution.close_question(connection.room_id)
            elif event_type == ClientEventType.ADMIN_REVEAL_ANSWER:
                result = self._execution.reveal_answer(connection.room_id)
            elif event_type in {
                ClientEventType.ADMIN_NEXT_QUESTION,
                ClientEventType.ADMIN_ADVANCE,
            }:
                room = self._rooms.get(connection.room_id)
                if room.state == RoomState.SECTION_BREAK:
                    result = self._execution.next_section(connection.room_id)
                else:
                    result = self._execution.next_question(connection.room_id)
            elif event_type == ClientEventType.ADMIN_NEXT_SECTION:
                result = self._execution.next_section(connection.room_id)
            elif event_type == ClientEventType.ADMIN_END_QUIZ:
                result = self._execution.end_quiz(connection.room_id)
            else:
                await self._manager.send_to_connection(
                    connection,
                    ServerEventType.ERROR,
                    make_error(
                        "VALIDATION_ERROR",
                        f"Unknown execution event '{event_type}'",
                    )["payload"],
                )
                return
        except QuizArenaError as exc:
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ERROR,
                make_error(exc.code, exc.message, details=exc.details)["payload"],
            )
            return

        for event in result.events:
            audience = getattr(event, "audience", "room")
            if audience == "admin":
                await self._manager.broadcast_to_admin(
                    connection.room_id,
                    event.type,
                    event.payload,
                )
            else:
                await self._manager.broadcast_to_room(
                    connection.room_id,
                    event.type,
                    event.payload,
                )

    async def _dispatch_answer_submit(
        self,
        connection: WSConnection,
        payload: dict[str, Any],
    ) -> None:
        if connection.participant_id is None:
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ANSWER_REJECTED,
                make_error("AUTH_ERROR", "Participant identity is required")["payload"],
            )
            return

        raw_ids = payload.get("optionIds", payload.get("selectedOptionIds"))
        if raw_ids is None:
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ANSWER_REJECTED,
                make_error("VALIDATION_ERROR", "payload.optionIds is required")["payload"],
            )
            return
        if not isinstance(raw_ids, list):
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ANSWER_REJECTED,
                make_error("VALIDATION_ERROR", "payload.optionIds must be an array")["payload"],
            )
            return

        try:
            option_ids = [UUID(str(item)) for item in raw_ids]
        except (TypeError, ValueError):
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ANSWER_REJECTED,
                make_error("VALIDATION_ERROR", "optionIds must be valid UUIDs")["payload"],
            )
            return

        # Prefer live connection presence; DB status is also checked in the service.
        if not self._manager.is_participant_connected(
            connection.room_id,
            connection.participant_id,
        ):
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ANSWER_REJECTED,
                make_error("FORBIDDEN", "Participant must be connected to submit an answer")[
                    "payload"
                ],
            )
            return

        try:
            result = self._responses.submit(
                room_id=connection.room_id,
                participant_id=connection.participant_id,
                option_ids=option_ids,
                require_connected=True,
            )
        except QuizArenaError as exc:
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ANSWER_REJECTED,
                make_error(exc.code, exc.message, details=exc.details)["payload"],
            )
            return

        for event in result.events:
            if event.audience == "participant":
                await self._manager.send_to_connection(connection, event.type, event.payload)
            elif event.audience == "admin":
                await self._manager.broadcast_to_admin(
                    connection.room_id,
                    event.type,
                    event.payload,
                )


def build_room_snapshot(room) -> dict[str, Any]:
    return {
        "id": str(room.id),
        "roomCode": room.room_code,
        "state": room.state.value,
        "lobbySubState": room.lobby_sub_state.value if room.lobby_sub_state else None,
        "quizTitle": room.quiz_title_snapshot,
        "codesExpired": room.codes_expired,
        "currentQuestionIndex": room.current_question_index,
    }


def build_participant_snapshot(
    participant,
    *,
    submission: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = {
        "id": str(participant.id),
        "displayName": participant.display_name,
        "state": participant.state.value,
        "connectionStatus": participant.connection_status.value,
        "totalScore": participant.total_score,
        "streak": participant.streak,
        "rank": participant.rank,
    }
    if submission is not None:
        data["hasSubmitted"] = submission.get("hasSubmitted", False)
        data["submission"] = submission
    return data


async def notify_participant_presence(
    manager: ConnectionManager,
    *,
    room_id: UUID,
    event_type: str,
    participant,
) -> None:
    """Admin-only presence events (emails included for admin monitoring)."""
    payload = {
        "participantId": str(participant.id),
        "displayName": participant.display_name,
        "email": participant.email,
        "state": participant.state.value,
        "connectionStatus": participant.connection_status.value,
        "totalScore": participant.total_score,
    }
    await manager.broadcast_to_admin(room_id, event_type, payload)
