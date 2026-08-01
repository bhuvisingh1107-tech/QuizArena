"""Scoring engine — evaluate responses and aggregate participant totals.

Does not compute rankings, leaderboards, podiums, or analytics.
Triggered after answer reveal (never while a question is Open).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.enums import ParticipantState, SessionQuestionState
from app.models.participant import Participant
from app.models.response import Response
from app.models.session_question import SessionQuestion
from app.repositories.live_room_repository import LiveRoomRepository
from app.repositories.participant_repository import ParticipantRepository
from app.repositories.response_repository import ResponseRepository
from app.services.state_machine import question_fsm


@dataclass
class ScoreBreakdown:
    is_correct: bool
    is_unanswered: bool
    base_points: int
    time_bonus: int
    streak_bonus: int
    total_points: int


@dataclass
class ScoringSummary:
    room_id: UUID
    question_id: UUID
    question_index: int | None
    total_submissions: int
    correct_count: int
    incorrect_count: int
    unanswered_count: int
    already_scored: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)


class ScoringService:
    """Score all responses for the current revealed question."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._rooms = LiveRoomRepository(session)
        self._responses = ResponseRepository(session)
        self._participants = ParticipantRepository(session)

    def score_question(self, room_id: UUID) -> ScoringSummary:
        """Score every participant for the current revealed question (idempotent)."""
        room = self._rooms.get_by_id(room_id)
        if room is None:
            raise NotFoundError("NOT_FOUND", "Live room not found")

        questions = sorted(room.session_questions, key=lambda q: q.sort_order)
        if room.current_question_index is None or not (
            0 <= room.current_question_index < len(questions)
        ):
            raise NotFoundError("NOT_FOUND", "No current question is available to score")

        question = questions[room.current_question_index]
        question_index = room.current_question_index

        if question.state == SessionQuestionState.OPEN:
            raise ValidationError(
                "QUESTION_STILL_OPEN",
                "Cannot score a question that is still Open",
            )

        if question.state not in {
            SessionQuestionState.REVEALED,
            SessionQuestionState.SCORED,
        }:
            raise ValidationError(
                "QUESTION_NOT_REVEALED",
                "Scoring requires the question to be Revealed",
            )

        if question.state == SessionQuestionState.SCORED:
            summary = self._build_summary(
                room_id=room_id,
                question=question,
                question_index=question_index,
                already_scored=True,
            )
            summary.events = [self._scored_event(summary)]
            return summary

        participants = [
            p
            for p in self._participants.list_for_room(room_id)
            if p.state not in {ParticipantState.BANNED, ParticipantState.KICKED}
        ]

        for participant in participants:
            response = self._responses.get_by_participant_and_question(
                participant.id,
                question.id,
            )
            if response is None:
                response = self._responses.create(
                    Response(
                        participant_id=participant.id,
                        session_question_id=question.id,
                        selected_option_ids=None,
                        is_correct=False,
                        is_unanswered=True,
                        base_points_earned=0,
                        time_bonus_earned=0,
                        streak_bonus_earned=0,
                        total_points_earned=0,
                        submitted_at=None,
                        response_time_ms=None,
                        status="unanswered",
                        scored_at=None,
                    )
                )
            elif response.scored_at is not None:
                continue

            self.score_response(response, question, participant, room.config)

        question.state = question_fsm.transition(question.state, "mark_scored")
        self._session.flush()
        self._session.commit()

        summary = self._build_summary(
            room_id=room_id,
            question=question,
            question_index=question_index,
            already_scored=False,
        )
        summary.events = [self._scored_event(summary)]

        # Personal feedback for each participant (used by participant client).
        for participant in participants:
            response = self._responses.get_by_participant_and_question(
                participant.id,
                question.id,
            )
            if response is None:
                continue
            summary.events.append(
                {
                    "type": "score:personal",
                    "payload": {
                        "roomId": str(room_id),
                        "questionId": str(question.id),
                        "questionIndex": question_index,
                        "participantId": str(participant.id),
                        "isCorrect": bool(response.is_correct),
                        "isUnanswered": bool(response.is_unanswered),
                        "basePoints": int(response.base_points_earned or 0),
                        "timeBonus": int(response.time_bonus_earned or 0),
                        "streakBonus": int(response.streak_bonus_earned or 0),
                        "pointsEarned": int(response.total_points_earned or 0),
                        "totalScore": int(participant.total_score or 0),
                        "streak": int(participant.streak or 0),
                    },
                    "audience": "participant",
                    "participantId": str(participant.id),
                }
            )

        from app.services.leaderboard_service import LeaderboardService

        board = LeaderboardService(self._session).snapshot(room_id)
        self._session.commit()
        summary.events.append(
            {
                "type": "leaderboard:updated",
                "payload": board,
                "audience": "room",
            }
        )
        return summary

    def score_response(
        self,
        response: Response,
        question: SessionQuestion,
        participant: Participant,
        room_config: Any | None,
    ) -> ScoreBreakdown:
        """Evaluate one response and update participant aggregates."""
        if response.session_question_id != question.id:
            raise ValidationError(
                "VALIDATION_ERROR",
                "Response does not belong to the current question",
            )

        if response.scored_at is not None:
            return ScoreBreakdown(
                is_correct=response.is_correct,
                is_unanswered=response.is_unanswered,
                base_points=response.base_points_earned,
                time_bonus=response.time_bonus_earned,
                streak_bonus=response.streak_bonus_earned,
                total_points=response.total_points_earned,
            )

        unanswered = self._is_unanswered(response)
        correct = False if unanswered else self._evaluate_correctness(response, question)

        base = question.base_points if correct else 0
        time_bonus = 0
        if (
            correct
            and not unanswered
            and room_config is not None
            and bool(getattr(room_config, "time_bonus_enabled", False))
            and response.response_time_ms is not None
            and question.time_limit_seconds
            and question.time_limit_seconds > 0
        ):
            limit_ms = int(question.time_limit_seconds) * 1000
            remaining_ratio = max(0.0, 1.0 - (response.response_time_ms / limit_ms))
            max_bonus = int(getattr(room_config, "time_bonus_max_points", 0) or 0)
            time_bonus = int(round(remaining_ratio * max_bonus))

        if unanswered or not correct:
            participant.streak = 0
            streak_bonus = 0
        else:
            participant.streak = int(participant.streak or 0) + 1
            streak_bonus = self._compute_streak_bonus(participant.streak, room_config)

        total = base + time_bonus + streak_bonus
        now = datetime.now(UTC)

        response.is_unanswered = unanswered
        response.is_correct = correct
        response.base_points_earned = base
        response.time_bonus_earned = time_bonus
        response.streak_bonus_earned = streak_bonus
        response.total_points_earned = total
        response.scored_at = now
        if unanswered:
            response.status = "unanswered"
        elif correct:
            response.status = "correct"
        else:
            response.status = "incorrect"

        participant.total_score = int(participant.total_score or 0) + total
        if unanswered:
            participant.unanswered_count = int(participant.unanswered_count or 0) + 1
        elif correct:
            participant.total_correct = int(participant.total_correct or 0) + 1
        else:
            participant.total_incorrect = int(participant.total_incorrect or 0) + 1

        self._session.flush()
        return ScoreBreakdown(
            is_correct=correct,
            is_unanswered=unanswered,
            base_points=base,
            time_bonus=time_bonus,
            streak_bonus=streak_bonus,
            total_points=total,
        )

    @staticmethod
    def _scored_event(summary: ScoringSummary) -> dict[str, Any]:
        return {
            "type": "question:scored",
            "payload": {
                "roomId": str(summary.room_id),
                "questionId": str(summary.question_id),
                "questionIndex": summary.question_index,
                "totalSubmissions": summary.total_submissions,
                "correctCount": summary.correct_count,
                "incorrectCount": summary.incorrect_count,
                "unansweredCount": summary.unanswered_count,
            },
            "audience": "admin",
        }

    def _build_summary(
        self,
        *,
        room_id: UUID,
        question: SessionQuestion,
        question_index: int | None,
        already_scored: bool,
    ) -> ScoringSummary:
        responses = self._responses.list_for_question(question.id)
        correct = 0
        incorrect = 0
        unanswered = 0
        submissions = 0
        for response in responses:
            if response.is_unanswered or response.submitted_at is None:
                unanswered += 1
            else:
                submissions += 1
                if response.is_correct:
                    correct += 1
                else:
                    incorrect += 1

        return ScoringSummary(
            room_id=room_id,
            question_id=question.id,
            question_index=question_index,
            total_submissions=submissions,
            correct_count=correct,
            incorrect_count=incorrect,
            unanswered_count=unanswered,
            already_scored=already_scored,
        )

    @staticmethod
    def _is_unanswered(response: Response) -> bool:
        if response.submitted_at is None:
            return True
        if response.is_unanswered:
            return True
        if not response.selected_option_ids:
            return True
        return False

    @staticmethod
    def _evaluate_correctness(response: Response, question: SessionQuestion) -> bool:
        """SR-003 / SR-004 — exact set match (all-or-nothing for multi-select)."""
        correct_ids = {opt.id for opt in question.options if opt.is_correct}
        try:
            selected = {UUID(str(oid)) for oid in (response.selected_option_ids or [])}
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "INVALID_OPTION",
                "Response contains invalid option identifiers",
            ) from exc

        option_ids = {opt.id for opt in question.options}
        if not selected.issubset(option_ids):
            raise ValidationError(
                "INVALID_OPTION",
                "Response references options that do not belong to this question",
            )

        return selected == correct_ids

    @staticmethod
    def _compute_streak_bonus(streak_after: int, room_config: Any | None) -> int:
        if room_config is None or not getattr(room_config, "streak_bonus_enabled", False):
            return 0
        if streak_after <= 1:
            return 0
        rules = getattr(room_config, "streak_bonus_rules", None) or {}
        per_level = rules.get("pointsPerLevel", rules.get("bonusPerLevel", 1))
        try:
            per = int(per_level)
        except (TypeError, ValueError):
            per = 1
        return max(0, per) * (streak_after - 1)
