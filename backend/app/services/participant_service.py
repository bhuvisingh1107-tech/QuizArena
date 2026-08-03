"""Participant join, reconnect, leave, and session lookup (API_SPEC.md §12)."""

from __future__ import annotations

import secrets
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.models.enums import (
    ConnectionStatus,
    LobbySubState,
    ParticipantState,
    RoomState,
)
from app.models.live_room import LiveRoom
from app.models.participant import Participant
from app.repositories.participant_repository import ParticipantRepository
from app.schemas.participant import JoinRequest
from app.services.state_machine import participant_fsm

_MAX_PARTICIPANTS_PER_ROOM = 100  # NFR-031 / OBJ-004
_MAX_TOKEN_ATTEMPTS = 16

_HOSTING_JOIN_STATES = {
    RoomState.LOBBY,
    RoomState.ACTIVE,
    RoomState.PAUSED,
    RoomState.SECTION_BREAK,
}


class ParticipantService:
    """Join validation, session token auth, reconnect, and leave."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._participants = ParticipantRepository(session)

    def join(self, payload: JoinRequest) -> tuple[Participant, LiveRoom, bool]:
        """
        Create or restore a participant.

        Returns (participant, room, restored).
        """
        room = self._participants.get_room_by_code(payload.room_code)
        if room is None:
            raise NotFoundError("INVALID_ROOM_CODE", "Invalid or unknown room code")

        self._ensure_room_joinable_base(room)

        if self._participants.is_email_banned(room.id, payload.email):
            raise ValidationError(
                "PARTICIPANT_BANNED",
                "This email is banned from rejoining this room",
            )

        existing = self._participants.get_by_room_and_email(room.id, payload.email)
        if existing is not None:
            return self._restore_existing(existing, room, payload.display_name)

        self._ensure_accepting_new_joins(room)

        name_owner = self._participants.get_by_room_and_display_name(
            room.id,
            payload.display_name,
        )
        if name_owner is not None:
            # Allow reclaiming a name after leave / session end (same display name, new device).
            if name_owner.state in {
                ParticipantState.SESSION_ENDED,
            } or (
                name_owner.connection_status == ConnectionStatus.DISCONNECTED
                and name_owner.state == ParticipantState.DISCONNECTED
                and name_owner.total_score == 0
                and name_owner.total_correct == 0
            ):
                # Soft-clear prior abandoned seat so the unique name can be reused.
                name_owner.display_name = f"{name_owner.display_name} (left-{str(name_owner.id)[:8]})"
                self._session.flush()
            else:
                raise ConflictError(
                    "DUPLICATE_DISPLAY_NAME",
                    "Display name is already taken in this room",
                )

        if self._participants.count_for_room(room.id) >= _MAX_PARTICIPANTS_PER_ROOM:
            raise ValidationError(
                "ROOM_FULL",
                f"Room has reached the maximum of {_MAX_PARTICIPANTS_PER_ROOM} participants",
            )

        state = participant_fsm.state_after_join(room.state)
        try:
            participant = self._participants.create(
                live_room_id=room.id,
                display_name=payload.display_name.strip(),
                email=payload.email,
                session_token=self._generate_session_token(),
                state=state,
                connection_status=ConnectionStatus.CONNECTED,
            )
            from app.services.session_event_service import PARTICIPANT_JOINED, log_session_event

            log_session_event(
                self._session,
                room.id,
                PARTICIPANT_JOINED,
                {
                    "participantId": str(participant.id),
                    "displayName": participant.display_name,
                },
                flush=False,
            )
            self._session.commit()
        except Exception as exc:
            self._session.rollback()
            from sqlalchemy.exc import IntegrityError

            if isinstance(exc, IntegrityError):
                raise ConflictError(
                    "DUPLICATE_DISPLAY_NAME",
                    "Display name is already taken in this room",
                ) from exc
            raise
        self._session.refresh(participant)
        from app.core.audit import audit

        audit(
            "participant.join",
            room_id=str(room.id),
            participant_id=str(participant.id),
            display_name=participant.display_name,
            restored=False,
        )
        return participant, room, False

    def get_by_token(self, session_token: str) -> Participant:
        participant = self._participants.get_by_session_token(session_token)
        if participant is None:
            raise AuthenticationError(
                "INVALID_PARTICIPANT_TOKEN",
                "Invalid or expired participant session token",
            )
        return participant

    def get_by_id_for_token(self, participant_id: UUID, session_token: str) -> Participant:
        participant = self.get_by_token(session_token)
        if participant.id != participant_id:
            raise AuthenticationError(
                "INVALID_PARTICIPANT_TOKEN",
                "Participant token does not match the requested participant",
            )
        return participant

    def reconnect(self, session_token: str) -> tuple[Participant, LiveRoom]:
        """Token-based reconnect — preserve score and restore connection."""
        participant = self.get_by_token(session_token)
        room = participant.live_room
        if room is None:
            raise NotFoundError("LIVE_ROOM_NOT_FOUND", "Live room not found")

        if room.codes_expired or room.state == RoomState.CLOSED:
            raise ValidationError("ROOM_CLOSED", "Room is closed")

        if participant.state == ParticipantState.BANNED:
            raise ValidationError(
                "PARTICIPANT_BANNED",
                "This participant is banned from the room",
            )
        if self._participants.is_email_banned(room.id, participant.email):
            raise ValidationError(
                "PARTICIPANT_BANNED",
                "This email is banned from rejoining this room",
            )

        new_state = participant_fsm.state_after_token_reconnect(room.state, participant.state)
        participant.state = new_state
        participant.connection_status = ConnectionStatus.CONNECTED
        # Keep the same session token for automatic client reconnect (FR-105).
        self._participants.flush()
        self._session.commit()
        self._session.refresh(participant)
        return participant, room

    def leave(self, session_token: str) -> Participant:
        participant = self.get_by_token(session_token)
        room = participant.live_room

        if participant.state in {ParticipantState.BANNED, ParticipantState.KICKED}:
            raise ValidationError(
                "INVALID_LEAVE",
                "Kicked or banned participants cannot leave via this endpoint",
            )
        if room is not None and room.state == RoomState.CLOSED:
            raise ValidationError("ROOM_CLOSED", "Room is closed")

        participant.state = ParticipantState.DISCONNECTED
        participant.connection_status = ConnectionStatus.DISCONNECTED
        from app.services.session_event_service import PARTICIPANT_LEFT, log_session_event

        log_session_event(
            self._session,
            participant.live_room_id,
            PARTICIPANT_LEFT,
            {
                "participantId": str(participant.id),
                "displayName": participant.display_name,
            },
            flush=False,
        )
        self._participants.flush()
        self._session.commit()
        self._session.refresh(participant)
        return participant

    def _restore_existing(
        self,
        existing: Participant,
        room: LiveRoom,
        display_name: str,
    ) -> tuple[Participant, LiveRoom, bool]:
        if existing.state == ParticipantState.BANNED:
            raise ValidationError(
                "PARTICIPANT_BANNED",
                "This participant is banned from the room",
            )
        if existing.display_name != display_name:
            raise ConflictError(
                "DISPLAY_NAME_MISMATCH",
                "Rejoin requires the same display name previously used with this email",
            )

        if room.state == RoomState.CLOSED or room.codes_expired:
            raise ValidationError("ROOM_CLOSED", "Room is closed")
        if room.state == RoomState.SETUP:
            raise ValidationError(
                "ROOM_NOT_ACCEPTING_JOINS",
                "Room lobby has not been opened yet",
            )
        if room.state == RoomState.COMPLETED:
            raise ValidationError(
                "ROOM_COMPLETED",
                "Cannot join a room that has already completed",
            )
        if room.state not in _HOSTING_JOIN_STATES:
            raise ValidationError(
                "ROOM_NOT_ACCEPTING_JOINS",
                f"Cannot rejoin a room in state '{room.state.value}'",
            )

        existing.state = participant_fsm.state_after_join(room.state)
        existing.connection_status = ConnectionStatus.CONNECTED
        existing.session_token = self._generate_session_token()
        self._participants.flush()
        self._session.commit()
        self._session.refresh(existing)
        return existing, room, True

    @staticmethod
    def _ensure_room_joinable_base(room: LiveRoom) -> None:
        if room.codes_expired or room.state == RoomState.CLOSED:
            raise ValidationError("ROOM_CLOSED", "Room is closed or the join code has expired")
        if room.state == RoomState.SETUP:
            raise ValidationError(
                "ROOM_NOT_ACCEPTING_JOINS",
                "Room lobby has not been opened yet",
            )

    @staticmethod
    def _ensure_accepting_new_joins(room: LiveRoom) -> None:
        if room.state == RoomState.COMPLETED:
            raise ValidationError(
                "ROOM_COMPLETED",
                "Cannot join a room that has already completed",
            )
        if room.state != RoomState.LOBBY:
            raise ValidationError(
                "ROOM_NOT_ACCEPTING_JOINS",
                "New participants may only join while the lobby is open",
            )
        if room.lobby_sub_state != LobbySubState.OPEN:
            raise ValidationError(
                "ROOM_NOT_ACCEPTING_JOINS",
                "Lobby is closed to new participants",
            )

    def _generate_session_token(self) -> str:
        for _ in range(_MAX_TOKEN_ATTEMPTS):
            token = secrets.token_urlsafe(32)[:64]
            if not self._participants.session_token_exists(token):
                return token
        raise ConflictError(
            "TOKEN_GENERATION_FAILED",
            "Unable to issue a participant session token; please retry",
        )
