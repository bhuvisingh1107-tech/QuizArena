"""Section data access (DATABASE_SCHEMA.md §6.2)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.section import Section


class SectionRepository:
    """Repository for quiz sections."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        quiz_id: UUID,
        name: str,
        sort_order: int,
    ) -> Section:
        section = Section(quiz_id=quiz_id, name=name, sort_order=sort_order)
        self._session.add(section)
        self._session.flush()
        return section

    def get_by_id(self, section_id: UUID) -> Section | None:
        return self._session.get(Section, section_id)

    def get_for_quiz(self, quiz_id: UUID, section_id: UUID) -> Section | None:
        stmt = select(Section).where(
            Section.id == section_id,
            Section.quiz_id == quiz_id,
        )
        return self._session.scalar(stmt)

    def list_for_quiz(self, quiz_id: UUID) -> list[Section]:
        stmt = (
            select(Section)
            .where(Section.quiz_id == quiz_id)
            .order_by(Section.sort_order.asc(), Section.created_at.asc())
        )
        return list(self._session.scalars(stmt).all())

    def count_for_quiz(self, quiz_id: UUID) -> int:
        stmt = select(func.count()).select_from(Section).where(Section.quiz_id == quiz_id)
        return int(self._session.scalar(stmt) or 0)

    def next_sort_order(self, quiz_id: UUID) -> int:
        stmt = select(func.max(Section.sort_order)).where(Section.quiz_id == quiz_id)
        current = self._session.scalar(stmt)
        return 0 if current is None else int(current) + 1

    def sort_order_taken(
        self,
        quiz_id: UUID,
        sort_order: int,
        *,
        exclude_section_id: UUID | None = None,
    ) -> bool:
        stmt = select(Section.id).where(
            Section.quiz_id == quiz_id,
            Section.sort_order == sort_order,
        )
        if exclude_section_id is not None:
            stmt = stmt.where(Section.id != exclude_section_id)
        return self._session.scalar(stmt) is not None

    def delete(self, section: Section) -> None:
        self._session.delete(section)
        self._session.flush()

    def flush(self) -> None:
        self._session.flush()
