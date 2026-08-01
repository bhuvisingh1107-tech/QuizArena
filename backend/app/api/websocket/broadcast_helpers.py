"""Shared helpers for broadcasting ExecutionResult / TargetedEvent over WebSockets."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.api.websocket.connection_manager import ConnectionManager, connection_manager


async def broadcast_execution_events(
    room_id: UUID,
    events: list[Any],
    *,
    manager: ConnectionManager | None = None,
) -> None:
    """Fan out execution/scoring events to admin, participant, or room audiences."""
    mgr = manager or connection_manager
    for event in events:
        audience = getattr(event, "audience", "room")
        event_type = getattr(event, "type", None)
        payload = getattr(event, "payload", {}) or {}
        participant_id = getattr(event, "participant_id", None)
        if event_type is None and isinstance(event, dict):
            audience = event.get("audience", "room")
            event_type = event.get("type")
            payload = event.get("payload") or {}
            pid = event.get("participantId") or event.get("participant_id")
            participant_id = UUID(str(pid)) if pid else None

        if not event_type:
            continue

        if audience == "admin":
            await mgr.broadcast_to_admin(room_id, event_type, payload)
        elif audience == "participant" and participant_id is not None:
            pool = mgr.get_room_pool(room_id)
            if pool and participant_id in pool.participants:
                await mgr.send_to_connection(
                    pool.participants[participant_id],
                    event_type,
                    payload,
                )
        else:
            await mgr.broadcast_to_room(room_id, event_type, payload)


def schedule_after_question_started(room_id: UUID, events: list[Any]) -> None:
    """Hook auto-progression after a question:started event is emitted."""
    from datetime import UTC, datetime

    from app.services.timer_service import auto_progression

    started = next((e for e in events if getattr(e, "type", None) == "question:started"), None)
    if started is None:
        return
    payload = getattr(started, "payload", {}) or {}
    q = payload.get("question") if isinstance(payload.get("question"), dict) else payload
    ends = payload.get("timerEndsAt") or (q or {}).get("timerEndsAt")
    qid = (q or {}).get("id")
    ends_epoch: float | None = None
    if isinstance(ends, str):
        try:
            ends_epoch = datetime.fromisoformat(ends.replace("Z", "+00:00")).timestamp()
        except ValueError:
            ends_epoch = None
    elif isinstance(ends, (int, float)):
        ends_epoch = float(ends)
    auto_progression.schedule_question(
        room_id,
        ends_at_epoch=ends_epoch,
        question_id=UUID(str(qid)) if qid else None,
    )
