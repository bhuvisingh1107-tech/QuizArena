"""Quiz execution engine — session snapshot traversal, reveal, and completion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.enums import (
    AnswerRevealBehavior,
    RoomState,
    SessionQuestionState,
)
from app.models.live_room import LiveRoom
from app.models.session_option import SessionOption
from app.models.session_question import SessionQuestion
from app.models.session_section import SessionSection
from app.repositories.live_room_repository import LiveRoomRepository
from app.services.state_machine import question_fsm, room_fsm


@dataclass
class BroadcastEvent:
    """Deferred WebSocket broadcast emitted by the execution service."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    audience: Literal["room", "admin", "participant"] = "room"
    participant_id: UUID | None = None


@dataclass
class ExecutionResult:
    room: LiveRoom
    events: list[BroadcastEvent] = field(default_factory=list)


@dataclass
class ExecutionState:
    """Read-only snapshot of current quiz execution for other modules."""

    room: LiveRoom
    question: SessionQuestion | None
    question_index: int | None
    is_accepting_answers: bool


class QuizExecutionService:
    """Control quiz progression over the immutable session snapshot."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._rooms = LiveRoomRepository(session)

    # ── Read-only execution state (for ResponseService, resync, etc.) ───────

    def get_execution_state(self, room_id: UUID) -> ExecutionState:
        """Expose current room/question execution state without mutating it."""
        room = self._require_room(room_id)
        question: SessionQuestion | None = None
        index = room.current_question_index
        if index is not None:
            questions = self._ordered_questions(room)
            if 0 <= index < len(questions):
                question = questions[index]
        accepting = (
            room.state == RoomState.ACTIVE
            and question is not None
            and question.state == SessionQuestionState.OPEN
        )
        return ExecutionState(
            room=room,
            question=question,
            question_index=index,
            is_accepting_answers=accepting,
        )

    # ── Public admin actions ───────────────────────────────────────────────

    def start_first_question(self, room_id: UUID) -> ExecutionResult:
        room = self._require_room(room_id)
        self._ensure_room_active(room)
        questions = self._ordered_questions(room)
        if not questions:
            raise ValidationError("SNAPSHOT_EMPTY", "Session snapshot has no questions")

        if any(
            q.state
            in {
                SessionQuestionState.OPEN,
                SessionQuestionState.CLOSED,
                SessionQuestionState.REVEALED,
                SessionQuestionState.SCORED,
                SessionQuestionState.BUZZER_OPEN,
                SessionQuestionState.BUZZER_LOCKED,
            }
            for q in questions
        ):
            raise ValidationError(
                "QUESTION_ALREADY_STARTED",
                "A question has already been started for this session",
            )

        room.current_question_index = 0
        question = questions[0]
        question.state = question_fsm.transition(question.state, "present")
        question.opened_at = datetime.now(UTC)
        section = self._section_for(room, question)
        events = [
            BroadcastEvent(
                type="section:started",
                payload=self._section_payload(room, section),
            ),
            BroadcastEvent(
                type="question:started",
                payload=self._question_payload(room, question, section, include_correct=False),
            ),
        ]
        room = self._commit(room)
        return ExecutionResult(room=room, events=events)

    def close_question(self, room_id: UUID) -> ExecutionResult:
        room = self._require_room(room_id)
        self._ensure_room_active(room)
        question = self._current_question(room)
        question.state = question_fsm.transition(question.state, "close")
        section = self._section_for(room, question)
        events = [
            BroadcastEvent(
                type="question:closed",
                payload=self._question_payload(room, question, section, include_correct=False),
            ),
        ]
        room = self._commit(room)
        return ExecutionResult(room=room, events=events)

    def reveal_answer(self, room_id: UUID) -> ExecutionResult:
        """Reveal correct answers, then invoke ScoringService (idempotent)."""
        from app.services.scoring_service import ScoringService

        room = self._require_room(room_id)
        self._ensure_room_active(room)
        question = self._current_question(room)
        section = self._section_for(room, question)

        if question.state == SessionQuestionState.SCORED:
            summary = ScoringService(self._session).score_question(room_id)
            events = [
                BroadcastEvent(
                    type="question:reveal",
                    payload=self._question_payload(
                        room, question, section, include_correct=True
                    ),
                ),
            ]
            for item in summary.events:
                pid = item.get("participantId")
                events.append(
                    BroadcastEvent(
                        type=item["type"],
                        payload=item["payload"],
                        audience=item.get("audience", "admin"),
                        participant_id=UUID(str(pid)) if pid else None,
                    )
                )
            return ExecutionResult(room=room, events=events)

        if question.state == SessionQuestionState.REVEALED:
            # Reveal already happened; ensure scoring completes idempotently.
            summary = ScoringService(self._session).score_question(room_id)
            room = self._rooms.get_by_id(room_id) or room
            events = [
                BroadcastEvent(
                    type="question:reveal",
                    payload=self._question_payload(
                        room,
                        self._current_question(room),
                        section,
                        include_correct=True,
                    ),
                ),
            ]
            for item in summary.events:
                pid = item.get("participantId")
                events.append(
                    BroadcastEvent(
                        type=item["type"],
                        payload=item["payload"],
                        audience=item.get("audience", "admin"),
                        participant_id=UUID(str(pid)) if pid else None,
                    )
                )
            return ExecutionResult(room=room, events=events)

        question.state = question_fsm.transition(question.state, "reveal")
        events = [
            BroadcastEvent(
                type="question:reveal",
                payload=self._question_payload(room, question, section, include_correct=True),
            ),
        ]
        room = self._commit(room)

        summary = ScoringService(self._session).score_question(room_id)
        room = self._rooms.get_by_id(room_id) or room
        for item in summary.events:
            pid = item.get("participantId")
            events.append(
                BroadcastEvent(
                    type=item["type"],
                    payload=item["payload"],
                    audience=item.get("audience", "admin"),
                    participant_id=UUID(str(pid)) if pid else None,
                )
            )
        return ExecutionResult(room=room, events=events)

    def next_question(self, room_id: UUID) -> ExecutionResult:
        room = self._require_room(room_id)
        self._ensure_room_active(room)
        questions = self._ordered_questions(room)
        current = self._current_question(room)
        self._finalize_current_for_advance(room, current)

        next_index = (room.current_question_index or 0) + 1
        if next_index >= len(questions):
            return self._complete_quiz(room)

        nxt = questions[next_index]
        current_section = self._section_for(room, current)
        next_section = self._section_for(room, nxt)

        if next_section.id != current_section.id:
            room.state = room_fsm.transition(room.state, "section_break")
            from app.services.display_stats_service import DisplayStatsService

            extras = DisplayStatsService(self._session).section_break_extras(
                room_id,
                current_section.id,
            )
            room = self._commit(room)
            return ExecutionResult(
                room=room,
                events=[
                    BroadcastEvent(
                        type="section:break",
                        payload={
                            **self._section_payload(room, current_section),
                            "completedQuestionIndex": room.current_question_index,
                            **extras,
                        },
                    ),
                    BroadcastEvent(
                        type="room:state_changed",
                        payload=self._room_state_payload(room),
                    ),
                ],
            )

        room.current_question_index = next_index
        nxt.state = question_fsm.transition(nxt.state, "present")
        nxt.opened_at = datetime.now(UTC)
        events = [
            BroadcastEvent(
                type="question:started",
                payload=self._question_payload(room, nxt, next_section, include_correct=False),
            ),
        ]
        room = self._commit(room)
        return ExecutionResult(room=room, events=events)

    def next_section(self, room_id: UUID) -> ExecutionResult:
        room = self._require_room(room_id)
        if room.state != RoomState.SECTION_BREAK:
            raise ValidationError(
                "INVALID_STATE_TRANSITION",
                "Next section is only allowed during SectionBreak",
            )
        questions = self._ordered_questions(room)
        next_index = (room.current_question_index or 0) + 1
        if next_index >= len(questions):
            return self._complete_quiz(room)

        nxt = questions[next_index]
        section = self._section_for(room, nxt)
        room.state = room_fsm.transition(room.state, "continue_section")
        room.current_question_index = next_index
        nxt.state = question_fsm.transition(nxt.state, "present")
        nxt.opened_at = datetime.now(UTC)
        events = [
            BroadcastEvent(
                type="section:continued",
                payload=self._section_payload(room, section),
            ),
            BroadcastEvent(
                type="section:started",
                payload=self._section_payload(room, section),
            ),
            BroadcastEvent(
                type="question:started",
                payload=self._question_payload(room, nxt, section, include_correct=False),
            ),
            BroadcastEvent(
                type="room:state_changed",
                payload=self._room_state_payload(room),
            ),
        ]
        room = self._commit(room)
        return ExecutionResult(room=room, events=events)

    def end_quiz(self, room_id: UUID) -> ExecutionResult:
        room = self._require_room(room_id)
        if room.state == RoomState.COMPLETED:
            raise ValidationError(
                "QUIZ_ALREADY_COMPLETED",
                "Quiz execution has already completed",
            )
        if room.state not in {RoomState.ACTIVE, RoomState.PAUSED, RoomState.SECTION_BREAK}:
            raise ValidationError(
                "INVALID_STATE_TRANSITION",
                f"Cannot end quiz while room is in state '{room.state.value}'",
            )
        # Best-effort close current open question without scoring.
        try:
            current = self._current_question(room)
            if current.state in {
                SessionQuestionState.OPEN,
                SessionQuestionState.BUZZER_OPEN,
                SessionQuestionState.BUZZER_LOCKED,
            }:
                current.state = question_fsm.transition(current.state, "close")
            if current.state in {SessionQuestionState.CLOSED, SessionQuestionState.REVEALED}:
                current.state = question_fsm.transition(current.state, "mark_scored")
        except ValidationError:
            pass

        return self._complete_quiz(room)

    # ── Internals ──────────────────────────────────────────────────────────

    def _finalize_current_for_advance(
        self,
        room: LiveRoom,
        current: SessionQuestion,
    ) -> None:
        """Ensure current question is eligible to leave before advancing."""
        if current.state == SessionQuestionState.OPEN:
            raise ValidationError(
                "QUESTION_STILL_OPEN",
                "Close the current question before advancing",
            )
        if current.state == SessionQuestionState.CLOSED:
            reveal = (
                room.config.answer_reveal_behavior
                if room.config is not None
                else AnswerRevealBehavior.AFTER_EACH
            )
            if reveal == AnswerRevealBehavior.AFTER_EACH:
                raise ValidationError(
                    "REVEAL_REQUIRED",
                    "Reveal the correct answer before advancing to the next question",
                )
            current.state = question_fsm.transition(current.state, "mark_scored")
            return
        if current.state == SessionQuestionState.REVEALED:
            current.state = question_fsm.transition(current.state, "mark_scored")
            return
        if current.state == SessionQuestionState.SCORED:
            return
        if current.state == SessionQuestionState.PENDING:
            raise ValidationError(
                "QUESTION_NOT_STARTED",
                "Start the current question before advancing",
            )
        raise ValidationError(
            "INVALID_QUESTION_TRANSITION",
            f"Cannot advance from question state '{current.state.value}'",
        )

    def _complete_quiz(self, room: LiveRoom) -> ExecutionResult:
        room.state = room_fsm.transition(room.state, "end")
        room.completed_at = datetime.now(UTC)
        from app.services.display_stats_service import DisplayStatsService
        from app.services.leaderboard_service import LeaderboardService

        board = LeaderboardService(self._session).snapshot(room.id)
        highlights = DisplayStatsService(self._session).session_highlights(room.id)
        events = [
            BroadcastEvent(
                type="quiz:completed",
                payload=self._completion_payload(room, board, highlights),
            ),
            BroadcastEvent(
                type="room:completed",
                payload=self._room_state_payload(room),
            ),
            BroadcastEvent(
                type="leaderboard:updated",
                payload=board,
            ),
        ]
        room = self._commit(room)
        return ExecutionResult(room=room, events=events)

    def _require_room(self, room_id: UUID) -> LiveRoom:
        room = self._rooms.get_by_id(room_id)
        if room is None:
            raise NotFoundError("LIVE_ROOM_NOT_FOUND", "Live room not found")
        return room

    @staticmethod
    def _ensure_room_active(room: LiveRoom) -> None:
        if room.state == RoomState.COMPLETED:
            raise ValidationError(
                "QUIZ_ALREADY_COMPLETED",
                "Cannot modify execution of a completed quiz",
            )
        if room.state != RoomState.ACTIVE:
            raise ValidationError(
                "ROOM_NOT_ACTIVE",
                f"Quiz execution requires an Active room (current: '{room.state.value}')",
            )

    @staticmethod
    def _ordered_questions(room: LiveRoom) -> list[SessionQuestion]:
        return sorted(room.session_questions, key=lambda q: q.sort_order)

    def _current_question(self, room: LiveRoom) -> SessionQuestion:
        questions = self._ordered_questions(room)
        if not questions:
            raise ValidationError("SNAPSHOT_EMPTY", "Session snapshot has no questions")
        if room.current_question_index is None:
            raise ValidationError(
                "QUESTION_NOT_STARTED",
                "No current question index is set; start the session first",
            )
        idx = room.current_question_index
        if idx < 0 or idx >= len(questions):
            raise ValidationError(
                "INVALID_QUESTION_INDEX",
                f"Current question index {idx} is out of range",
            )
        return questions[idx]

    @staticmethod
    def _section_for(room: LiveRoom, question: SessionQuestion) -> SessionSection:
        for section in room.session_sections:
            if section.id == question.session_section_id:
                return section
        raise ValidationError(
            "SECTION_NOT_FOUND",
            "Session section for the current question was not found in the snapshot",
        )

    def _commit(self, room: LiveRoom) -> LiveRoom:
        self._rooms.flush()
        self._session.commit()
        refreshed = self._rooms.get_by_id(room.id)
        assert refreshed is not None
        return refreshed

    def _question_payload(
        self,
        room: LiveRoom,
        question: SessionQuestion,
        section: SessionSection,
        *,
        include_correct: bool,
    ) -> dict[str, Any]:
        explanation = None
        if include_correct and question.source_question_id is not None:
            from app.models.question import Question

            source = self._session.get(Question, question.source_question_id)
            if source is not None:
                explanation = source.explanation

        reveal_behavior = (
            room.config.answer_reveal_behavior.value
            if room.config is not None
            else AnswerRevealBehavior.AFTER_EACH.value
        )

        payload: dict[str, Any] = {
            "roomId": str(room.id),
            "questionIndex": room.current_question_index,
            "totalQuestions": len(room.session_questions),
            "answerRevealBehavior": reveal_behavior,
            "section": {
                "id": str(section.id),
                "name": section.name,
                "sortOrder": section.sort_order,
            },
            "question": {
                "id": str(question.id),
                "sectionId": str(question.session_section_id),
                "questionType": question.question_type.value,
                "promptText": question.prompt_text,
                "mediaFileId": str(question.media_file_id) if question.media_file_id else None,
                "basePoints": question.base_points,
                "timeLimitSeconds": question.time_limit_seconds,
                "timerEndsAt": self._timer_ends_at_ts(room, question),
                "timerPaused": room.state == RoomState.PAUSED,
                "allowMultipleCorrect": question.allow_multiple_correct,
                "sortOrder": question.sort_order,
                "state": question.state.value,
                "explanation": explanation if include_correct else None,
                "options": [
                    self._option_payload(opt, include_correct=include_correct)
                    for opt in sorted(question.options, key=lambda o: o.sort_order)
                ],
            },
        }
        # Convert timerEndsAt to ISO string for clients
        ends_ts = payload["question"]["timerEndsAt"]
        if isinstance(ends_ts, (int, float)):
            payload["question"]["timerEndsAt"] = (
                datetime.fromtimestamp(ends_ts, tz=UTC).isoformat().replace("+00:00", "Z")
            )
            payload["timerEndsAt"] = payload["question"]["timerEndsAt"]

        if include_correct:
            from app.services.display_stats_service import DisplayStatsService

            extras = DisplayStatsService(self._session).reveal_payload_extras(question)
            payload.update(extras)
            payload["question"]["explanation"] = extras.get("explanation") or explanation
        return payload

    @staticmethod
    def _timer_ends_at_ts(room: LiveRoom, question: SessionQuestion) -> float | None:
        if question.opened_at is None or not question.time_limit_seconds:
            return None
        pause_ms = int(room.pause_accumulated_ms or 0)
        if room.paused_at is not None:
            pause_ms += max(
                0,
                int((datetime.now(UTC) - room.paused_at).total_seconds() * 1000),
            )
        return (
            question.opened_at.timestamp()
            + int(question.time_limit_seconds)
            + (pause_ms / 1000.0)
        )

    @staticmethod
    def _option_payload(option: SessionOption, *, include_correct: bool) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(option.id),
            "text": option.text,
            "sortOrder": option.sort_order,
        }
        if include_correct:
            data["isCorrect"] = option.is_correct
        return data

    def _section_payload(self, room: LiveRoom, section: SessionSection) -> dict[str, Any]:
        count = sum(1 for q in room.session_questions if q.session_section_id == section.id)
        return {
            "roomId": str(room.id),
            "section": {
                "id": str(section.id),
                "name": section.name,
                "sortOrder": section.sort_order,
                "questionCount": count,
            },
            "currentQuestionIndex": room.current_question_index,
        }

    @staticmethod
    def _room_state_payload(room: LiveRoom) -> dict[str, Any]:
        return {
            "roomId": str(room.id),
            "state": room.state.value,
            "lobbySubState": room.lobby_sub_state.value if room.lobby_sub_state else None,
            "currentQuestionIndex": room.current_question_index,
            "codesExpired": room.codes_expired,
            "completedAt": room.completed_at.isoformat() if room.completed_at else None,
        }

    @staticmethod
    def _completion_payload(
        room: LiveRoom,
        board: dict[str, Any] | None = None,
        highlights: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        board = board or {}
        highlights = highlights or {}
        return {
            "roomId": str(room.id),
            "state": room.state.value,
            "currentQuestionIndex": room.current_question_index,
            "completedAt": room.completed_at.isoformat() if room.completed_at else None,
            "totalQuestions": len(room.session_questions),
            "podium": board.get("podium") or highlights.get("podium"),
            "leaderboard": board.get("entries") or highlights.get("leaderboard"),
            "participantCount": board.get("participantCount")
            or highlights.get("participantCount"),
            "averageScore": highlights.get("averageScore"),
            "winner": highlights.get("winner"),
            "hardestQuestion": highlights.get("hardestQuestion"),
            "mostMissedQuestion": highlights.get("mostMissedQuestion"),
            "fastestAnswer": highlights.get("fastestAnswer"),
        }
