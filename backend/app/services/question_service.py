"""Question CRUD business logic (API_SPEC.md §9)."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.enums import QuizStatus
from app.models.question import Question
from app.repositories.question_repository import QuestionRepository
from app.repositories.quiz_repository import QuizRepository
from app.repositories.section_repository import SectionRepository
from app.schemas.question import QuestionCreateRequest, QuestionUpdateRequest

_MUTABLE_QUIZ_STATUSES = {QuizStatus.DRAFT, QuizStatus.READY}
_MAX_QUESTIONS_PER_QUIZ = 100  # FR-017


class QuestionService:
    """Question create / list / get / update / delete within a section."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._quizzes = QuizRepository(session)
        self._sections = SectionRepository(session)
        self._questions = QuestionRepository(session)

    def create(
        self,
        quiz_id: UUID,
        section_id: UUID,
        payload: QuestionCreateRequest,
    ) -> Question:
        quiz = self._require_parent_quiz(quiz_id)
        self._ensure_quiz_mutable(quiz.status)
        self._require_section(quiz_id, section_id)

        if self._questions.count_for_quiz(quiz_id) >= _MAX_QUESTIONS_PER_QUIZ:
            raise ValidationError(
                "QUESTION_LIMIT_EXCEEDED",
                f"A quiz may contain at most {_MAX_QUESTIONS_PER_QUIZ} questions",
            )

        sort_order = (
            payload.sort_order
            if payload.sort_order is not None
            else self._questions.next_sort_order(section_id)
        )
        self._ensure_sort_order_available(section_id, sort_order)

        question = self._questions.create(
            section_id=section_id,
            question_type=payload.question_type,
            prompt_text=payload.prompt_text,
            explanation=payload.explanation,
            base_points=payload.base_points,
            time_limit_seconds=payload.time_limit_seconds,
            allow_multiple_correct=payload.allow_multiple_correct,
            sort_order=sort_order,
        )
        self._demote_ready_if_needed(quiz)
        self._session.commit()
        self._session.refresh(question)
        return question

    def list(self, quiz_id: UUID, section_id: UUID) -> tuple[list[Question], int]:
        self._require_parent_quiz(quiz_id)
        self._require_section(quiz_id, section_id)
        items = self._questions.list_for_section(section_id)
        return items, len(items)

    def get(self, quiz_id: UUID, section_id: UUID, question_id: UUID) -> Question:
        self._require_parent_quiz(quiz_id)
        self._require_section(quiz_id, section_id)
        question = self._questions.get_for_section(section_id, question_id)
        if question is None:
            raise NotFoundError("QUESTION_NOT_FOUND", "Question not found")
        return question

    def update(
        self,
        quiz_id: UUID,
        section_id: UUID,
        question_id: UUID,
        payload: QuestionUpdateRequest,
    ) -> Question:
        quiz = self._require_parent_quiz(quiz_id)
        self._ensure_quiz_mutable(quiz.status)
        self._require_section(quiz_id, section_id)
        question = self.get(quiz_id, section_id, question_id)

        if payload.question_type is not None:
            question.question_type = payload.question_type
        if payload.prompt_text is not None:
            question.prompt_text = payload.prompt_text
        if payload.explanation is not None:
            question.explanation = payload.explanation
        if payload.base_points is not None:
            question.base_points = payload.base_points
        if payload.time_limit_seconds is not None:
            question.time_limit_seconds = payload.time_limit_seconds
        if payload.allow_multiple_correct is not None:
            question.allow_multiple_correct = payload.allow_multiple_correct
        if payload.sort_order is not None and payload.sort_order != question.sort_order:
            self._ensure_sort_order_available(
                section_id,
                payload.sort_order,
                exclude_question_id=question.id,
            )
            question.sort_order = payload.sort_order
        if payload.clear_media:
            question.media_file_id = None

        self._demote_ready_if_needed(quiz)
        self._questions.flush()
        self._session.commit()
        self._session.refresh(question)
        return question

    def delete(self, quiz_id: UUID, section_id: UUID, question_id: UUID) -> None:
        quiz = self._require_parent_quiz(quiz_id)
        self._ensure_quiz_mutable(quiz.status)
        self._require_section(quiz_id, section_id)
        question = self.get(quiz_id, section_id, question_id)
        self._questions.delete(question)
        self._demote_ready_if_needed(quiz)
        self._session.commit()

    def _require_parent_quiz(self, quiz_id: UUID):
        quiz = self._quizzes.get_by_id(quiz_id, include_deleted=False)
        if quiz is None:
            raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")
        return quiz

    def _require_section(self, quiz_id: UUID, section_id: UUID):
        section = self._sections.get_for_quiz(quiz_id, section_id)
        if section is None:
            raise NotFoundError("SECTION_NOT_FOUND", "Section not found")
        return section

    @staticmethod
    def _ensure_quiz_mutable(status: QuizStatus) -> None:
        if status == QuizStatus.IN_USE:
            raise ConflictError(
                "QUIZ_IN_USE",
                "Cannot modify questions of a quiz that is currently in use by a live room",
            )
        if status not in _MUTABLE_QUIZ_STATUSES:
            raise ValidationError(
                "QUIZ_NOT_EDITABLE",
                f"Cannot modify questions when quiz status is '{status.value}'",
            )

    def _ensure_sort_order_available(
        self,
        section_id: UUID,
        sort_order: int,
        *,
        exclude_question_id: UUID | None = None,
    ) -> None:
        if self._questions.sort_order_taken(
            section_id,
            sort_order,
            exclude_question_id=exclude_question_id,
        ):
            raise ConflictError(
                "DUPLICATE_SORT_ORDER",
                f"Sort order {sort_order} is already used by another question in this section",
            )

    @staticmethod
    def _demote_ready_if_needed(quiz) -> None:
        if quiz.status == QuizStatus.READY:
            quiz.status = QuizStatus.DRAFT
