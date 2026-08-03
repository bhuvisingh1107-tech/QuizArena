"""Answer submission — persist participant responses and score immediately.

Scoring on submit powers the live leaderboard (updates after every answer).
Reveal still scores unanswered responses and broadcasts answer reveal UI.
Duplicate submits for the same question are rejected (ALREADY_SUBMITTED).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from app.models.enums import (
    ConnectionStatus,
    ParticipantState,
    RoomState,
    SessionQuestionState,
)
from app.models.response import Response
from app.repositories.participant_repository import ParticipantRepository
from app.repositories.response_repository import ResponseRepository
from app.services.quiz_execution_service import QuizExecutionService


@dataclass
class TargetedEvent:
    """WebSocket event with an explicit audience (never leak selected answers)."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    audience: Literal["participant", "admin", "room"] = "participant"


@dataclass
class SubmitResult:
    response: Response
    events: list[TargetedEvent] = field(default_factory=list)
    already_submitted: bool = False
    all_eligible_answered: bool = False


class ResponseService:
    """Validate and persist answer submissions while a question is Open."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._responses = ResponseRepository(session)
        self._participants = ParticipantRepository(session)
        self._execution = QuizExecutionService(session)

    def submit(
        self,
        *,
        room_id: UUID,
        participant_id: UUID,
        option_ids: list[UUID],
        require_connected: bool = True,
    ) -> SubmitResult:
        if participant_id is None:
            raise AuthenticationError("AUTH_ERROR", "Participant identity is required")

        participant = self._participants.get_by_id(participant_id)
        if participant is None:
            raise NotFoundError("NOT_FOUND", "Participant not found")

        if participant.live_room_id != room_id:
            raise AuthorizationError(
                "FORBIDDEN",
                "Participant does not belong to this room",
            )

        if participant.state in {ParticipantState.BANNED, ParticipantState.KICKED}:
            raise AuthorizationError(
                "FORBIDDEN",
                "Banned or kicked participants cannot submit answers",
            )

        if self._participants.is_email_banned(room_id, participant.email):
            raise AuthorizationError(
                "FORBIDDEN",
                "Banned participants cannot submit answers",
            )

        if require_connected and participant.connection_status != ConnectionStatus.CONNECTED:
            raise AuthorizationError(
                "FORBIDDEN",
                "Participant must be connected to submit an answer",
            )

        try:
            execution = self._execution.get_execution_state(room_id)
        except NotFoundError:
            raise NotFoundError("NOT_FOUND", "Live room not found") from None
        room = execution.room

        if room.state == RoomState.COMPLETED:
            raise ValidationError(
                "ROOM_COMPLETED",
                "Cannot submit answers after the quiz has completed",
            )

        if room.state != RoomState.ACTIVE:
            raise ValidationError(
                "VALIDATION_ERROR",
                f"Cannot submit answers while room is in state '{room.state.value}'",
            )

        question = execution.question
        if question is None:
            raise NotFoundError("NOT_FOUND", "No current question is available")

        if question.state != SessionQuestionState.OPEN:
            raise ValidationError(
                "QUESTION_CLOSED",
                "Answers are only accepted while the current question is Open",
            )

        normalized_ids = self._normalize_option_ids(option_ids)
        self._validate_options(question, normalized_ids)

        existing = self._responses.get_by_participant_and_question(
            participant.id,
            question.id,
        )
        if existing is not None and existing.submitted_at is not None and not existing.is_unanswered:
            # DATABASE_SCHEMA: duplicate submit ignored — no mutation; signal client.
            raise ValidationError(
                "ALREADY_SUBMITTED",
                "An answer has already been submitted for this question",
            )

        now = datetime.now(UTC)
        id_strings = [str(oid) for oid in normalized_ids]
        response_time_ms: int | None = None
        if question.opened_at is not None:
            opened_at = question.opened_at
            if opened_at.tzinfo is None:
                opened_at = opened_at.replace(tzinfo=UTC)
            elapsed_ms = int((now - opened_at).total_seconds() * 1000)
            pause_ms = int(room.pause_accumulated_ms or 0)
            if room.paused_at is not None:
                paused_at = room.paused_at
                if paused_at.tzinfo is None:
                    paused_at = paused_at.replace(tzinfo=UTC)
                pause_ms += max(0, int((now - paused_at).total_seconds() * 1000))
            response_time_ms = max(0, elapsed_ms - pause_ms)

        response = Response(
            participant_id=participant.id,
            session_question_id=question.id,
            selected_option_ids=id_strings,
            is_correct=False,
            is_unanswered=False,
            base_points_earned=0,
            time_bonus_earned=0,
            streak_bonus_earned=0,
            total_points_earned=0,
            submitted_at=now,
            response_time_ms=response_time_ms,
            status="submitted",
        )
        try:
            self._responses.create(response)
            participant.state = ParticipantState.ANSWERED
            # Score immediately so the live leaderboard updates on every submit.
            # score_question at reveal skips already-scored rows and scores unanswered.
            from app.services.scoring_service import ScoringService

            ScoringService(self._session).score_response(
                response,
                question,
                participant,
                room.config,
            )
            from app.services.session_event_service import ANSWER_SUBMITTED, log_session_event

            log_session_event(
                self._session,
                room_id,
                ANSWER_SUBMITTED,
                {
                    "participantId": str(participant.id),
                    "displayName": participant.display_name,
                    "questionId": str(question.id),
                    "questionIndex": execution.question_index,
                    "responseTimeMs": response.response_time_ms,
                },
                flush=False,
            )
            self._session.commit()
        except Exception as exc:
            self._session.rollback()
            from sqlalchemy.exc import IntegrityError

            if isinstance(exc, IntegrityError):
                raise ValidationError(
                    "ALREADY_SUBMITTED",
                    "An answer has already been submitted for this question",
                ) from exc
            raise
        self._session.refresh(response)
        self._session.refresh(participant)

        submitted_count = self._responses.count_submitted_for_question(question.id)
        participant_count = self._participants.count_for_room(room_id)
        eligible_count = self._count_eligible_participants(room_id)
        all_answered = eligible_count > 0 and submitted_count >= eligible_count

        from app.services.leaderboard_service import LeaderboardService

        board = LeaderboardService(self._session).snapshot(room_id)
        self._session.commit()

        accept_payload = {
            "roomId": str(room_id),
            "questionId": str(question.id),
            "questionIndex": execution.question_index,
            "responseId": str(response.id),
            "selectedOptionIds": id_strings,
            "submittedAt": now.isoformat(),
            "responseTimeMs": response.response_time_ms,
            # Keep the public submit ack as "submitted" so clients do not treat
            # answer:accepted as pre-reveal correctness feedback.
            "status": "submitted",
            "pointsEarned": int(response.total_points_earned or 0),
            "totalScore": int(participant.total_score or 0),
            "streak": int(participant.streak or 0),
        }
        admin_count_payload = {
            "roomId": str(room_id),
            "questionId": str(question.id),
            "questionIndex": execution.question_index,
            "submittedCount": submitted_count,
            "participantCount": participant_count,
            "eligibleCount": eligible_count,
            "allAnswered": all_answered,
        }
        admin_received_payload = {
            "roomId": str(room_id),
            "questionId": str(question.id),
            "questionIndex": execution.question_index,
            "submittedCount": submitted_count,
        }

        return SubmitResult(
            response=response,
            events=[
                TargetedEvent(type="answer:accepted", payload=accept_payload, audience="participant"),
                TargetedEvent(
                    type="answer:received",
                    payload=admin_received_payload,
                    audience="admin",
                ),
                TargetedEvent(
                    type="answer:submission_count",
                    payload=admin_count_payload,
                    audience="room",
                ),
                TargetedEvent(
                    type="leaderboard:updated",
                    payload=board,
                    audience="room",
                ),
            ],
            all_eligible_answered=all_answered,
        )

    def _count_eligible_participants(self, room_id: UUID) -> int:
        excluded = {
            ParticipantState.BANNED,
            ParticipantState.KICKED,
            ParticipantState.SESSION_ENDED,
        }
        return sum(
            1
            for p in self._participants.list_for_room(room_id)
            if p.state not in excluded
        )

    def get_submission_status(
        self,
        *,
        room_id: UUID,
        participant_id: UUID,
    ) -> dict[str, Any]:
        """Resync helper: whether the participant has answered the current question."""
        execution = self._execution.get_execution_state(room_id)
        question = execution.question
        if question is None:
            return {
                "hasSubmitted": False,
                "questionId": None,
                "selectedOptionIds": None,
                "status": None,
            }
        existing = self._responses.get_by_participant_and_question(participant_id, question.id)
        submitted = (
            existing is not None
            and existing.submitted_at is not None
            and not existing.is_unanswered
        )
        return {
            "hasSubmitted": submitted,
            "questionId": str(question.id),
            "questionIndex": execution.question_index,
            "questionState": question.state.value,
            "selectedOptionIds": list(existing.selected_option_ids or []) if submitted else None,
            "status": existing.status if submitted and existing is not None else None,
            "submittedAt": existing.submitted_at.isoformat() if submitted and existing else None,
        }

    @staticmethod
    def _normalize_option_ids(option_ids: list[UUID]) -> list[UUID]:
        if not option_ids:
            raise ValidationError(
                "VALIDATION_ERROR",
                "At least one optionId is required",
            )
        # Preserve order, drop duplicates
        seen: set[UUID] = set()
        normalized: list[UUID] = []
        for oid in option_ids:
            if oid in seen:
                continue
            seen.add(oid)
            normalized.append(oid)
        return normalized

    @staticmethod
    def _validate_options(question, option_ids: list[UUID]) -> None:
        valid_ids = {opt.id for opt in question.options}
        for oid in option_ids:
            if oid not in valid_ids:
                raise ValidationError(
                    "INVALID_OPTION",
                    "One or more selected options do not belong to the current question",
                )
        if not question.allow_multiple_correct and len(option_ids) > 1:
            raise ValidationError(
                "VALIDATION_ERROR",
                "This question accepts only a single selected option",
            )
