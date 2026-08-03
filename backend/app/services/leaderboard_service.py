"""Live leaderboard ranking and broadcast payloads."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.live_room import LiveRoom
from app.models.response import Response
from app.models.session_question import SessionQuestion
from app.repositories.participant_repository import ParticipantRepository
from app.services.results_service import assign_competition_ranks


class LeaderboardService:
    """Compute room leaderboard snapshots for WebSocket broadcasts."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._participants = ParticipantRepository(session)

    def snapshot(self, room_id: UUID) -> dict:
        participants = self._participants.list_for_room(room_id)
        ranked = assign_competition_ranks(participants)

        latest_by_participant = self._latest_responses_for_current_question(room_id)

        entries = []
        for rp in ranked:
            latest = latest_by_participant.get(rp.participant.id)
            time_bonus = int(latest.time_bonus_earned or 0) if latest else 0
            entries.append(
                {
                    "rank": rp.rank,
                    "participantId": str(rp.participant.id),
                    "displayName": rp.participant.display_name,
                    "score": int(rp.participant.total_score or 0),
                    "streak": int(rp.participant.streak or 0),
                    "timeBonus": time_bonus,
                    "lastTimeBonus": time_bonus,
                    "lastIsCorrect": (
                        None
                        if latest is None
                        else bool(latest.is_correct) and not bool(latest.is_unanswered)
                    ),
                }
            )
        for rp in ranked:
            rp.participant.rank = rp.rank
        self._session.flush()

        podium = {
            "entries": [
                {
                    "rank": e["rank"] if e["rank"] in (1, 2, 3) else idx + 1,
                    "participantId": e["participantId"],
                    "displayName": e["displayName"],
                    "score": e["score"],
                    "streak": e["streak"],
                }
                for idx, e in enumerate(entries[:3])
            ]
        }
        return {
            "roomId": str(room_id),
            "entries": entries,
            "leaderboard": entries,
            "podium": podium,
            "participantCount": len(participants),
        }

    def _latest_responses_for_current_question(self, room_id: UUID) -> dict[UUID, Response]:
        room = self._session.get(LiveRoom, room_id)
        if room is None or room.current_question_index is None:
            return {}
        # Session snapshot sets sort_order == question index.
        question_id = self._session.scalar(
            select(SessionQuestion.id).where(
                SessionQuestion.live_room_id == room_id,
                SessionQuestion.sort_order == int(room.current_question_index),
            ),
        )
        if question_id is None:
            return {}
        responses = self._session.scalars(
            select(Response).where(Response.session_question_id == question_id),
        ).all()
        return {response.participant_id: response for response in responses}

    def personal_payloads(self, room_id: UUID) -> list[tuple[UUID, dict]]:
        """Per-participant rank/score messages after scoring."""
        participants = self._participants.list_for_room(room_id)
        ranked = assign_competition_ranks(participants)
        out: list[tuple[UUID, dict]] = []
        for rp in ranked:
            out.append(
                (
                    rp.participant.id,
                    {
                        "roomId": str(room_id),
                        "yourRank": rp.rank,
                        "yourScore": int(rp.participant.total_score or 0),
                        "streak": int(rp.participant.streak or 0),
                        "totalCorrect": int(rp.participant.total_correct or 0),
                        "totalIncorrect": int(rp.participant.total_incorrect or 0),
                        "unansweredCount": int(rp.participant.unanswered_count or 0),
                    },
                )
            )
        return out
