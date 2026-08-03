"""Append session timeline events for export and diagnostics."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.session_event import SessionEvent


# Canonical event_type values used across live services.
ROOM_CREATED = "room_created"
LOBBY_OPENED = "lobby_opened"
QUIZ_STARTED = "quiz_started"
QUESTION_SHOWN = "question_shown"
ANSWER_SUBMITTED = "answer_submitted"
PARTICIPANT_JOINED = "participant_joined"
PARTICIPANT_LEFT = "participant_left"
REVEAL = "reveal"
NEXT = "next"
PAUSE = "pause"
RESUME = "resume"
QUIZ_ENDED = "quiz_ended"
AWAITING_HOST_ADVANCE = "awaiting_host_advance"

# Human-readable labels for Excel Timeline sheet.
TIMELINE_LABELS: dict[str, str] = {
    ROOM_CREATED: "Room Created",
    LOBBY_OPENED: "Room Created",
    QUIZ_STARTED: "Quiz Started",
    QUESTION_SHOWN: "Question Shown",
    ANSWER_SUBMITTED: "Answer Submitted",
    PARTICIPANT_JOINED: "Participant Joined",
    PARTICIPANT_LEFT: "Participant Left",
    REVEAL: "Reveal",
    NEXT: "Next Question",
    QUIZ_ENDED: "Quiz Ended",
    PAUSE: "Pause",
    RESUME: "Resume",
    AWAITING_HOST_ADVANCE: "Awaiting Host Advance",
}


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
