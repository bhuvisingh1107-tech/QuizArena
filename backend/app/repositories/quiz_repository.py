"""Quiz data access (DATABASE_SCHEMA.md §6.1)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import QuizStatus
from app.models.quiz import Quiz
from app.models.quiz_config import QuizConfig


class QuizRepository:
    """Repository for Quiz templates and related QuizConfig."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        title: str,
        description: str | None,
        config: QuizConfig,
        owner_id: UUID | None = None,
    ) -> Quiz:
        quiz = Quiz(
            title=title,
            description=description,
            status=QuizStatus.DRAFT,
            config=config,
            owner_id=owner_id,
        )
        self._session.add(quiz)
        self._session.flush()
        return quiz

    def get_by_id(
        self,
        quiz_id: UUID,
        *,
        include_deleted: bool = False,
        owner_id: UUID | None = None,
    ) -> Quiz | None:
        stmt = (
            select(Quiz)
            .options(selectinload(Quiz.config))
            .where(Quiz.id == quiz_id)
        )
        if not include_deleted:
            stmt = stmt.where(Quiz.status != QuizStatus.DELETED)
        if owner_id is not None:
            stmt = stmt.where(Quiz.owner_id == owner_id)
        return self._session.scalar(stmt)

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: QuizStatus | None = None,
        search: str | None = None,
        include_deleted: bool = False,
        include_archived: bool = True,
        owner_id: UUID | None = None,
    ) -> tuple[list[Quiz], int]:
        filters = []
        if owner_id is not None:
            filters.append(Quiz.owner_id == owner_id)
        if status is not None:
            filters.append(Quiz.status == status)
        else:
            if not include_deleted:
                filters.append(Quiz.status != QuizStatus.DELETED)
            if not include_archived:
                filters.append(Quiz.status != QuizStatus.ARCHIVED)

        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(Quiz.title.ilike(pattern), Quiz.description.ilike(pattern)),
            )

        count_stmt = select(func.count()).select_from(Quiz)
        list_stmt = (
            select(Quiz)
            .options(selectinload(Quiz.config))
            .order_by(Quiz.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        for condition in filters:
            count_stmt = count_stmt.where(condition)
            list_stmt = list_stmt.where(condition)

        total = int(self._session.scalar(count_stmt) or 0)
        items = list(self._session.scalars(list_stmt).all())
        return items, total

    def delete(self, quiz: Quiz) -> None:
        self._session.delete(quiz)
        self._session.flush()

    def flush(self) -> None:
        self._session.flush()
