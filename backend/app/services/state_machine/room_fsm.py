"""Room state transition rules (PROJECT_SPEC.md §13.1, SYSTEM_ARCHITECTURE.md §7)."""

from app.core.exceptions import ValidationError
from app.models.enums import RoomState

# Room lifecycle including section breaks used by quiz execution.
_TRANSITIONS: dict[tuple[RoomState, str], RoomState] = {
    (RoomState.SETUP, "open_lobby"): RoomState.LOBBY,
    (RoomState.LOBBY, "start"): RoomState.ACTIVE,
    (RoomState.LOBBY, "close"): RoomState.CLOSED,
    (RoomState.ACTIVE, "pause"): RoomState.PAUSED,
    (RoomState.ACTIVE, "end"): RoomState.COMPLETED,
    (RoomState.ACTIVE, "section_break"): RoomState.SECTION_BREAK,
    (RoomState.PAUSED, "resume"): RoomState.ACTIVE,
    (RoomState.PAUSED, "end"): RoomState.COMPLETED,
    (RoomState.SECTION_BREAK, "continue_section"): RoomState.ACTIVE,
    (RoomState.SECTION_BREAK, "end"): RoomState.COMPLETED,
    (RoomState.COMPLETED, "close"): RoomState.CLOSED,
}


def transition(current: RoomState, action: str) -> RoomState:
    """Return the next room state or raise on an invalid transition."""
    next_state = _TRANSITIONS.get((current, action))
    if next_state is None:
        raise ValidationError(
            "INVALID_STATE_TRANSITION",
            f"Cannot '{action}' a room in state '{current.value}'",
        )
    return next_state


def is_hosting_state(state: RoomState) -> bool:
    """States that count toward the single active room constraint (RS-003)."""
    return state in {
        RoomState.SETUP,
        RoomState.LOBBY,
        RoomState.ACTIVE,
        RoomState.PAUSED,
        RoomState.SECTION_BREAK,
    }
