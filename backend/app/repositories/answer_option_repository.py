"""Answer option data access (DATABASE_SCHEMA.md §6.4)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.answer_option import AnswerOption


class AnswerOptionRepository:
    """Repository for question answer options."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        question_id: UUID,
        text: str,
        is_correct: bool,
        sort_order: int,
    ) -> AnswerOption:
        option = AnswerOption(
            question_id=question_id,
            text=text,
            is_correct=is_correct,
            sort_order=sort_order,
        )
        self._session.add(option)
        self._session.flush()
        return option

    def get_by_id(self, option_id: UUID) -> AnswerOption | None:
        return self._session.get(AnswerOption, option_id)

    def get_for_question(self, question_id: UUID, option_id: UUID) -> AnswerOption | None:
        stmt = select(AnswerOption).where(
            AnswerOption.id == option_id,
            AnswerOption.question_id == question_id,
        )
        return self._session.scalar(stmt)

    def list_for_question(self, question_id: UUID) -> list[AnswerOption]:
        stmt = (
            select(AnswerOption)
            .where(AnswerOption.question_id == question_id)
            .order_by(AnswerOption.sort_order.asc(), AnswerOption.created_at.asc())
        )
        return list(self._session.scalars(stmt).all())

    def count_for_question(self, question_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(AnswerOption)
            .where(AnswerOption.question_id == question_id)
        )
        return int(self._session.scalar(stmt) or 0)

    def count_correct_for_question(
        self,
        question_id: UUID,
        *,
        exclude_option_id: UUID | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(AnswerOption)
            .where(
                AnswerOption.question_id == question_id,
                AnswerOption.is_correct.is_(True),
            )
        )
        if exclude_option_id is not None:
            stmt = stmt.where(AnswerOption.id != exclude_option_id)
        return int(self._session.scalar(stmt) or 0)

    def next_sort_order(self, question_id: UUID) -> int:
        stmt = select(func.max(AnswerOption.sort_order)).where(
            AnswerOption.question_id == question_id,
        )
        current = self._session.scalar(stmt)
        return 0 if current is None else int(current) + 1

    def sort_order_taken(
        self,
        question_id: UUID,
        sort_order: int,
        *,
        exclude_option_id: UUID | None = None,
    ) -> bool:
        stmt = select(AnswerOption.id).where(
            AnswerOption.question_id == question_id,
            AnswerOption.sort_order == sort_order,
        )
        if exclude_option_id is not None:
            stmt = stmt.where(AnswerOption.id != exclude_option_id)
        return self._session.scalar(stmt) is not None

    def delete(self, option: AnswerOption) -> None:
        self._session.delete(option)
        self._session.flush()

    def flush(self) -> None:
        self._session.flush()
