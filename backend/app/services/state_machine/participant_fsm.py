"""Participant join / reconnect helpers (PROJECT_SPEC.md §13.4)."""

from app.core.exceptions import ValidationError
from app.models.enums import ParticipantState, RoomState


def state_after_join(room_state: RoomState) -> ParticipantState:
    """Choose participant state after successful join/restore."""
    if room_state == RoomState.LOBBY:
        return ParticipantState.IN_LOBBY
    if room_state in {
        RoomState.ACTIVE,
        RoomState.PAUSED,
        RoomState.SECTION_BREAK,
    }:
        return ParticipantState.ACTIVE
    if room_state == RoomState.COMPLETED:
        return ParticipantState.SESSION_ENDED
    raise ValidationError(
        "ROOM_NOT_ACCEPTING_JOINS",
        f"Cannot join a room in state '{room_state.value}'",
    )


def state_after_token_reconnect(
    room_state: RoomState,
    previous: ParticipantState,
) -> ParticipantState:
    """Restore an appropriate state after token-based reconnect."""
    if previous in {ParticipantState.BANNED, ParticipantState.KICKED}:
        raise ValidationError(
            "INVALID_RECONNECT",
            "Kicked or banned participants cannot reconnect with a session token",
        )
    if room_state == RoomState.CLOSED:
        raise ValidationError("ROOM_CLOSED", "Room is closed")
    if room_state == RoomState.COMPLETED:
        return ParticipantState.SESSION_ENDED
    if room_state == RoomState.LOBBY:
        return ParticipantState.IN_LOBBY
    if room_state in {
        RoomState.ACTIVE,
        RoomState.PAUSED,
        RoomState.SECTION_BREAK,
    }:
        # Preserve in-question states when still mid-session.
        if previous in {
            ParticipantState.ANSWERING,
            ParticipantState.ANSWERED,
            ParticipantState.WAITING,
            ParticipantState.BUZZING,
            ParticipantState.BUZZ_UNLOCKED,
            ParticipantState.ACTIVE,
        }:
            return previous
        return ParticipantState.ACTIVE
    raise ValidationError(
        "INVALID_RECONNECT",
        f"Cannot reconnect while room is in state '{room_state.value}'",
    )
