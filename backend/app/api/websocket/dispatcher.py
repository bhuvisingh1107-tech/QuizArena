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
            if not await self._ensure_admin_token_valid(connection):
                return
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

    async def _ensure_admin_token_valid(self, connection: WSConnection) -> bool:
        """Reject admin control events after JWT expiry (connect-time auth alone is not enough)."""
        if not connection.auth_token:
            return True
        from app.config import get_settings
        from app.core.security import TokenValidationError, validate_access_token

        try:
            validate_access_token(connection.auth_token, get_settings())
            return True
        except TokenValidationError as exc:
            await self._manager.send_to_connection(
                connection,
                ServerEventType.ERROR,
                make_error(exc.code, exc.message)["payload"],
            )
            await self._manager.close_connection(
                connection,
                code=4003,
                reason=exc.code,
            )
            return False

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

        room_payload: dict[str, Any] = {
            "roomId": str(room.id),
            "state": room.state.value,
            "lobbySubState": room.lobby_sub_state.value if room.lobby_sub_state else None,
            "codesExpired": room.codes_expired,
        }
        if method_name in {"pause", "resume"}:
            execution = self._execution.get_execution_state(connection.room_id)
            if execution.question is not None:
                ends = QuizExecutionService._timer_ends_at_ts(room, execution.question)
                if ends is not None:
                    from datetime import UTC, datetime

                    ends_at = (
                        datetime.fromtimestamp(ends, tz=UTC)
                        .isoformat()
                        .replace("+00:00", "Z")
                    )
                    room_payload["timerEndsAt"] = ends_at
                    room_payload["timerPaused"] = room.state == RoomState.PAUSED
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

        # Start Quiz → open first question automatically and schedule progression.
        if method_name == "start":
            try:
                result = self._execution.start_first_question(connection.room_id)
            except QuizArenaError as exc:
                await self._manager.send_to_connection(
                    connection,
                    ServerEventType.ERROR,
                    make_error(exc.code, exc.message, details=exc.details)["payload"],
                )
                return
            from app.api.websocket.broadcast_helpers import (
                broadcast_execution_events,
                schedule_after_question_started,
            )

            await broadcast_execution_events(
                connection.room_id,
                result.events,
                manager=self._manager,
            )
            schedule_after_question_started(connection.room_id, result.events)

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

        from app.api.websocket.broadcast_helpers import (
            broadcast_execution_events,
            schedule_after_question_started,
        )

        await broadcast_execution_events(
            connection.room_id,
            result.events,
            manager=self._manager,
        )
        if event_type in {
            ClientEventType.ADMIN_START_QUESTION,
            ClientEventType.ADMIN_NEXT_QUESTION,
            ClientEventType.ADMIN_ADVANCE,
            ClientEventType.ADMIN_NEXT_SECTION,
        }:
            schedule_after_question_started(connection.room_id, result.events)
        if event_type in {
            ClientEventType.ADMIN_END_QUIZ,
            ClientEventType.ADMIN_CLOSE_QUESTION,
        }:
            from app.services.timer_service import auto_progression

            if event_type == ClientEventType.ADMIN_END_QUIZ:
                auto_progression.cancel_room(connection.room_id)

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
            elif event.audience == "room":
                await self._manager.broadcast_to_room(
                    connection.room_id,
                    event.type,
                    event.payload,
                )

        if result.all_eligible_answered:
            from app.services.timer_service import auto_progression

            auto_progression.notify_all_answered(connection.room_id)


def build_room_snapshot(room) -> dict[str, Any]:
    return {
        "id": str(room.id),
        "roomCode": room.room_code,
        "state": room.state.value,
        "lobbySubState": room.lobby_sub_state.value if room.lobby_sub_state else None,
        "quizTitle": room.quiz_title_snapshot,
        "codesExpired": room.codes_expired,
        "currentQuestionIndex": room.current_question_index,
        "hostName": "Host",
    }


def count_active_participants(session: Session, room_id: UUID) -> int:
    from app.models.enums import ParticipantState
    from app.repositories.participant_repository import ParticipantRepository

    participants = ParticipantRepository(session).list_for_room(room_id)
    return sum(
        1
        for p in participants
        if p.state
        not in {
            ParticipantState.BANNED,
            ParticipantState.KICKED,
            ParticipantState.SESSION_ENDED,
        }
    )


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
    session: Session | None = None,
) -> None:
    """Admin presence events plus room-wide participant count for lobby UIs."""
    payload = {
        "participantId": str(participant.id),
        "displayName": participant.display_name,
        "email": participant.email,
        "state": participant.state.value,
        "connectionStatus": participant.connection_status.value,
        "totalScore": participant.total_score,
    }
    await manager.broadcast_to_admin(room_id, event_type, payload)

    if session is not None:
        count = count_active_participants(session, room_id)
        await manager.broadcast_to_room(
            room_id,
            "participant:count",
            {
                "roomId": str(room_id),
                "participantCount": count,
            },
        )
