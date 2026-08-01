"""Question data access (DATABASE_SCHEMA.md §6.3)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import QuestionType
from app.models.question import Question


class QuestionRepository:
    """Repository for section questions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        section_id: UUID,
        question_type: QuestionType,
        prompt_text: str,
        base_points: int,
        time_limit_seconds: int | None,
        allow_multiple_correct: bool,
        sort_order: int,
        explanation: str | None = None,
    ) -> Question:
        question = Question(
            section_id=section_id,
            question_type=question_type,
            prompt_text=prompt_text,
            explanation=explanation,
            base_points=base_points,
            time_limit_seconds=time_limit_seconds,
            allow_multiple_correct=allow_multiple_correct,
            sort_order=sort_order,
        )
        self._session.add(question)
        self._session.flush()
        return question

    def get_by_id(self, question_id: UUID) -> Question | None:
        return self._session.get(Question, question_id)

    def get_for_section(self, section_id: UUID, question_id: UUID) -> Question | None:
        stmt = select(Question).where(
            Question.id == question_id,
            Question.section_id == section_id,
        )
        return self._session.scalar(stmt)

    def list_for_section(self, section_id: UUID) -> list[Question]:
        stmt = (
            select(Question)
            .where(Question.section_id == section_id)
            .order_by(Question.sort_order.asc(), Question.created_at.asc())
        )
        return list(self._session.scalars(stmt).all())

    def count_for_section(self, section_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Question)
            .where(Question.section_id == section_id)
        )
        return int(self._session.scalar(stmt) or 0)

    def count_for_quiz(self, quiz_id: UUID) -> int:
        from app.models.section import Section

        stmt = (
            select(func.count())
            .select_from(Question)
            .join(Section, Question.section_id == Section.id)
            .where(Section.quiz_id == quiz_id)
        )
        return int(self._session.scalar(stmt) or 0)

    def next_sort_order(self, section_id: UUID) -> int:
        stmt = select(func.max(Question.sort_order)).where(Question.section_id == section_id)
        current = self._session.scalar(stmt)
        return 0 if current is None else int(current) + 1

    def sort_order_taken(
        self,
        section_id: UUID,
        sort_order: int,
        *,
        exclude_question_id: UUID | None = None,
    ) -> bool:
        stmt = select(Question.id).where(
            Question.section_id == section_id,
            Question.sort_order == sort_order,
        )
        if exclude_question_id is not None:
            stmt = stmt.where(Question.id != exclude_question_id)
        return self._session.scalar(stmt) is not None

    def delete(self, question: Question) -> None:
        self._session.delete(question)
        self._session.flush()

    def flush(self) -> None:
        self._session.flush()
