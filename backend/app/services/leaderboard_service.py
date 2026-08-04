"""Live leaderboard ranking and broadcast payloads."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import SessionQuestionState
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

    def snapshot(self, room_id: UUID, *, include_correctness: bool | None = None) -> dict:
        """Build a leaderboard payload.

        ``lastIsCorrect`` is omitted unless the current question is Revealed/Scored
        (or ``include_correctness`` is forced True). Scores reflect totals already
        applied by ScoringService — which only runs at reveal.
        """
        participants = self._participants.list_for_room(room_id)
        ranked = assign_competition_ranks(participants)

        question = self._current_question(room_id)
        if include_correctness is None:
            include_correctness = question is not None and question.state in {
                SessionQuestionState.REVEALED,
                SessionQuestionState.SCORED,
            }

        latest_by_participant: dict[UUID, Response] = {}
        if include_correctness and question is not None:
            latest_by_participant = self._responses_for_question(question.id)

        entries = []
        for rp in ranked:
            latest = latest_by_participant.get(rp.participant.id)
            time_bonus = int(latest.time_bonus_earned or 0) if latest else 0
            entry: dict = {
                "rank": rp.rank,
                "participantId": str(rp.participant.id),
                "displayName": rp.participant.display_name,
                "score": int(rp.participant.total_score or 0),
                "streak": int(rp.participant.streak or 0),
                "timeBonus": time_bonus,
                "lastTimeBonus": time_bonus,
            }
            if include_correctness:
                entry["lastIsCorrect"] = (
                    None
                    if latest is None
                    else bool(latest.is_correct) and not bool(latest.is_unanswered)
                )
            entries.append(entry)
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

    def _current_question(self, room_id: UUID) -> SessionQuestion | None:
        room = self._session.get(LiveRoom, room_id)
        if room is None or room.current_question_index is None:
            return None
        return self._session.scalar(
            select(SessionQuestion).where(
                SessionQuestion.live_room_id == room_id,
                SessionQuestion.sort_order == int(room.current_question_index),
            ),
        )

    def _responses_for_question(self, question_id: UUID) -> dict[UUID, Response]:
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
