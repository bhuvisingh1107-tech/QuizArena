"""Answer option CRUD business logic (API_SPEC.md §9, PROJECT_SPEC FR-023/029)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.answer_option import AnswerOption
from app.models.enums import QuizStatus
from app.models.question import Question
from app.repositories.answer_option_repository import AnswerOptionRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.quiz_repository import QuizRepository
from app.repositories.section_repository import SectionRepository
from app.schemas.answer_option import AnswerOptionCreateRequest, AnswerOptionUpdateRequest
from app.services.question_crypto import open_option_fields, seal_option_fields

_MUTABLE_QUIZ_STATUSES = {QuizStatus.DRAFT, QuizStatus.READY}
_MAX_OPTIONS_PER_QUESTION = 6  # FR-029


class AnswerOptionService:
    """Answer option create / list / get / update / delete within a question."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._quizzes = QuizRepository(session)
        self._sections = SectionRepository(session)
        self._questions = QuestionRepository(session)
        self._options = AnswerOptionRepository(session)

    def create(
        self,
        quiz_id: UUID,
        section_id: UUID,
        question_id: UUID,
        payload: AnswerOptionCreateRequest,
        *,
        owner_id: UUID | None = None,
    ) -> AnswerOption:
        quiz = self._require_parent_quiz(quiz_id, owner_id=owner_id)
        self._ensure_quiz_mutable(quiz.status)
        self._require_section(quiz_id, section_id)
        question = self._require_question(section_id, question_id)

        if self._options.count_for_question(question_id) >= _MAX_OPTIONS_PER_QUESTION:
            raise ValidationError(
                "OPTION_LIMIT_EXCEEDED",
                f"A question may have at most {_MAX_OPTIONS_PER_QUESTION} answer options",
            )

        sort_order = (
            payload.sort_order
            if payload.sort_order is not None
            else self._options.next_sort_order(question_id)
        )
        self._ensure_sort_order_available(question_id, sort_order)

        if payload.is_correct:
            self._ensure_correct_flag_allowed(question, marking_correct=True)

        sealed_text, sealed_correct = seal_option_fields(payload.text, payload.is_correct)
        option = self._options.create(
            question_id=question_id,
            text=sealed_text,
            is_correct=sealed_correct,
            sort_order=sort_order,
        )
        self._demote_ready_if_needed(quiz)
        self._session.commit()
        self._session.refresh(option)
        return option

    def list(
        self,
        quiz_id: UUID,
        section_id: UUID,
        question_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> tuple[list[AnswerOption], int]:
        self._require_parent_quiz(quiz_id, owner_id=owner_id)
        self._require_section(quiz_id, section_id)
        self._require_question(section_id, question_id)
        items = self._options.list_for_question(question_id)
        return items, len(items)

    def get(
        self,
        quiz_id: UUID,
        section_id: UUID,
        question_id: UUID,
        option_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> AnswerOption:
        self._require_parent_quiz(quiz_id, owner_id=owner_id)
        self._require_section(quiz_id, section_id)
        self._require_question(section_id, question_id)
        option = self._options.get_for_question(question_id, option_id)
        if option is None:
            raise NotFoundError("ANSWER_OPTION_NOT_FOUND", "Answer option not found")
        return option

    def update(
        self,
        quiz_id: UUID,
        section_id: UUID,
        question_id: UUID,
        option_id: UUID,
        payload: AnswerOptionUpdateRequest,
        *,
        owner_id: UUID | None = None,
    ) -> AnswerOption:
        quiz = self._require_parent_quiz(quiz_id, owner_id=owner_id)
        self._ensure_quiz_mutable(quiz.status)
        self._require_section(quiz_id, section_id)
        question = self._require_question(section_id, question_id)
        option = self.get(quiz_id, section_id, question_id, option_id, owner_id=owner_id)
        current_text, current_correct = open_option_fields(option.text, option.is_correct)

        next_text = payload.text if payload.text is not None else current_text
        next_correct = (
            payload.is_correct if payload.is_correct is not None else current_correct
        )

        if payload.is_correct is not None and payload.is_correct != current_correct:
            if payload.is_correct:
                self._ensure_correct_flag_allowed(
                    question,
                    marking_correct=True,
                    exclude_option_id=option.id,
                )

        if next_text != current_text or next_correct != current_correct:
            option.text, option.is_correct = seal_option_fields(next_text, next_correct)

        if payload.sort_order is not None and payload.sort_order != option.sort_order:
            self._ensure_sort_order_available(
                question_id,
                payload.sort_order,
                exclude_option_id=option.id,
            )
            option.sort_order = payload.sort_order

        self._demote_ready_if_needed(quiz)
        self._options.flush()
        self._session.commit()
        self._session.refresh(option)
        return option

    def delete(
        self,
        quiz_id: UUID,
        section_id: UUID,
        question_id: UUID,
        option_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> None:
        quiz = self._require_parent_quiz(quiz_id, owner_id=owner_id)
        self._ensure_quiz_mutable(quiz.status)
        self._require_section(quiz_id, section_id)
        self._require_question(section_id, question_id)
        option = self.get(quiz_id, section_id, question_id, option_id, owner_id=owner_id)
        self._options.delete(option)
        self._demote_ready_if_needed(quiz)
        self._session.commit()

    def _require_parent_quiz(self, quiz_id: UUID, *, owner_id: UUID | None = None):
        quiz = self._quizzes.get_by_id(
            quiz_id,
            include_deleted=False,
            owner_id=owner_id,
        )
        if quiz is None:
            raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")
        return quiz

    def _require_section(self, quiz_id: UUID, section_id: UUID):
        section = self._sections.get_for_quiz(quiz_id, section_id)
        if section is None:
            raise NotFoundError("SECTION_NOT_FOUND", "Section not found")
        return section

    def _require_question(self, section_id: UUID, question_id: UUID) -> Question:
        question = self._questions.get_for_section(section_id, question_id)
        if question is None:
            raise NotFoundError("QUESTION_NOT_FOUND", "Question not found")
        return question

    @staticmethod
    def _ensure_quiz_mutable(status: QuizStatus) -> None:
        if status == QuizStatus.IN_USE:
            raise ConflictError(
                "QUIZ_IN_USE",
                "Cannot modify options of a quiz that is currently in use by a live room",
            )
        if status not in _MUTABLE_QUIZ_STATUSES:
            raise ValidationError(
                "QUIZ_NOT_EDITABLE",
                f"Cannot modify options when quiz status is '{status.value}'",
            )

    def _ensure_sort_order_available(
        self,
        question_id: UUID,
        sort_order: int,
        *,
        exclude_option_id: UUID | None = None,
    ) -> None:
        if self._options.sort_order_taken(
            question_id,
            sort_order,
            exclude_option_id=exclude_option_id,
        ):
            raise ConflictError(
                "DUPLICATE_SORT_ORDER",
                f"Sort order {sort_order} is already used by another option on this question",
            )

    def _ensure_correct_flag_allowed(
        self,
        question: Question,
        *,
        marking_correct: bool,
        exclude_option_id: UUID | None = None,
    ) -> None:
        """Respect allow_multiple_correct when marking options correct (FR-023)."""
        if not marking_correct:
            return
        if question.allow_multiple_correct:
            return
        existing = [
            opt
            for opt in self._options.list_for_question(question.id)
            if exclude_option_id is None or opt.id != exclude_option_id
        ]
        existing_correct = sum(
            1 for opt in existing if open_option_fields(opt.text, opt.is_correct)[1]
        )
        if existing_correct >= 1:
            raise ValidationError(
                "SINGLE_CORRECT_VIOLATION",
                "This question allows only one correct answer option "
                "(allowMultipleCorrect is false)",
            )

    @staticmethod
    def _demote_ready_if_needed(quiz) -> None:
        if quiz.status == QuizStatus.READY:
            quiz.status = QuizStatus.DRAFT
