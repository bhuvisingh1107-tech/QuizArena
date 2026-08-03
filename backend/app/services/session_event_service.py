"""Append session timeline events for export and diagnostics."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.session_event import SessionEvent


# Canonical event_type values used across live services.
LOBBY_OPENED = "lobby_opened"
QUIZ_STARTED = "quiz_started"
QUESTION_SHOWN = "question_shown"
ANSWER_SUBMITTED = "answer_submitted"
REVEAL = "reveal"
NEXT = "next"
PAUSE = "pause"
RESUME = "resume"
QUIZ_ENDED = "quiz_ended"
AWAITING_HOST_ADVANCE = "awaiting_host_advance"


def log_session_event(
    session: Session,
    live_room_id: UUID,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    flush: bool = True,
) -> SessionEvent:
    """Persist a timeline row. Caller owns the surrounding transaction/commit."""
    event = SessionEvent(
        live_room_id=live_room_id,
        event_type=event_type,
        payload_json=payload,
    )
    session.add(event)
    if flush:
        session.flush()
    return event
