"""Append session timeline events for export and diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.session_event import SessionEvent


# Canonical event_type values used across live services.
ROOM_CREATED = "room_created"
HOST_JOINED = "host_joined"
LOBBY_OPENED = "lobby_opened"
QUIZ_STARTED = "quiz_started"
QUESTION_SHOWN = "question_shown"  # legacy alias retained for older rows
QUESTION_BROADCAST = "question_broadcast"
QUESTION_OPEN = "question_open"
ANSWER_SUBMITTED = "answer_submitted"
PARTICIPANT_JOINED = "participant_joined"
PARTICIPANT_LEFT = "participant_left"
REVEAL = "reveal"  # legacy
REVEAL_STARTED = "reveal_started"
REVEAL_FINISHED = "reveal_finished"
LEADERBOARD_UPDATED = "leaderboard_updated"
NEXT = "next"
PAUSE = "pause"
RESUME = "resume"
QUIZ_ENDED = "quiz_ended"
AWAITING_HOST_ADVANCE = "awaiting_host_advance"

# Human-readable labels for Excel Timeline sheet.
TIMELINE_LABELS: dict[str, str] = {
    ROOM_CREATED: "Room Created",
    HOST_JOINED: "Host Joined",
    LOBBY_OPENED: "Lobby Opened",
    QUIZ_STARTED: "Quiz Started",
    QUESTION_SHOWN: "Question Broadcast",
    QUESTION_BROADCAST: "Question Broadcast",
    QUESTION_OPEN: "Question Open",
    ANSWER_SUBMITTED: "Answer Submitted",
    PARTICIPANT_JOINED: "Participant Joined",
    PARTICIPANT_LEFT: "Participant Left",
    REVEAL: "Reveal Started",
    REVEAL_STARTED: "Reveal Started",
    REVEAL_FINISHED: "Reveal Finished",
    LEADERBOARD_UPDATED: "Leaderboard Updated",
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
    created_at: datetime | None = None,
    flush: bool = True,
) -> SessionEvent:
    """Persist a timeline row. Caller owns the surrounding transaction/commit."""
    event = SessionEvent(
        live_room_id=live_room_id,
        event_type=event_type,
        payload_json=payload,
    )
    if created_at is not None:
        event.created_at = created_at
    session.add(event)
    if flush:
        session.flush()
    return event
