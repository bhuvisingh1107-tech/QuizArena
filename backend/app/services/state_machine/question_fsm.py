"""Session question live-state transitions (PROJECT_SPEC.md §13.3.2).

Scoring is a no-op marker state in this module — points are not calculated here.
"""

from app.core.exceptions import ValidationError
from app.models.enums import SessionQuestionState

_TRANSITIONS: dict[tuple[SessionQuestionState, str], SessionQuestionState] = {
    (SessionQuestionState.PENDING, "present"): SessionQuestionState.OPEN,
    (SessionQuestionState.OPEN, "close"): SessionQuestionState.CLOSED,
    (SessionQuestionState.BUZZER_OPEN, "close"): SessionQuestionState.CLOSED,
    (SessionQuestionState.BUZZER_LOCKED, "close"): SessionQuestionState.CLOSED,
    (SessionQuestionState.CLOSED, "reveal"): SessionQuestionState.REVEALED,
    (SessionQuestionState.CLOSED, "mark_scored"): SessionQuestionState.SCORED,
    (SessionQuestionState.REVEALED, "mark_scored"): SessionQuestionState.SCORED,
}


def transition(current: SessionQuestionState, action: str) -> SessionQuestionState:
    next_state = _TRANSITIONS.get((current, action))
    if next_state is None:
        raise ValidationError(
            "INVALID_QUESTION_TRANSITION",
            f"Cannot '{action}' a question in state '{current.value}'",
        )
    return next_state
