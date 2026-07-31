"""Answer submission — persist participant responses (no scoring).

Duplicate submits for the same question are rejected (ALREADY_SUBMITTED).
PROJECT_SPEC FR-072 allows changing selections before the first Submit;
post-submit updates are not supported (DATABASE_SCHEMA.md idempotent lock).
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
    """WebSocket event with an explicit audience (never cross-broadcast answers)."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    audience: Literal["participant", "admin"] = "participant"


@dataclass
class SubmitResult:
    response: Response
    events: list[TargetedEvent] = field(default_factory=list)
    already_submitted: bool = False


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
            response_time_ms=None,  # timers deferred
            status="submitted",
        )
        self._responses.create(response)
        participant.state = ParticipantState.ANSWERED
        self._session.commit()
        self._session.refresh(response)

        submitted_count = self._responses.count_submitted_for_question(question.id)
        participant_count = self._participants.count_for_room(room_id)

        accept_payload = {
            "roomId": str(room_id),
            "questionId": str(question.id),
            "questionIndex": execution.question_index,
            "responseId": str(response.id),
            "selectedOptionIds": id_strings,
            "submittedAt": now.isoformat(),
            "responseTimeMs": response.response_time_ms,
            "status": response.status,
        }
        admin_count_payload = {
            "roomId": str(room_id),
            "questionId": str(question.id),
            "questionIndex": execution.question_index,
            "submittedCount": submitted_count,
            "participantCount": participant_count,
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
                    audience="admin",
                ),
            ],
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
