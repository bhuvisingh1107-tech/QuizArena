"""Section CRUD business logic (API_SPEC.md §9)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.enums import QuizStatus
from app.models.section import Section
from app.repositories.quiz_repository import QuizRepository
from app.repositories.section_repository import SectionRepository
from app.schemas.section import SectionCreateRequest, SectionUpdateRequest

# Content edits only when quiz is Draft or Ready (mirrors quiz edit rules).
_MUTABLE_QUIZ_STATUSES = {QuizStatus.DRAFT, QuizStatus.READY}


class SectionService:
    """Section create / list / get / update / delete within a quiz."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._quizzes = QuizRepository(session)
        self._sections = SectionRepository(session)

    def create(
        self,
        quiz_id: UUID,
        payload: SectionCreateRequest,
        *,
        owner_id: UUID | None = None,
    ) -> Section:
        quiz = self._require_parent_quiz(quiz_id, owner_id=owner_id)
        self._ensure_quiz_mutable(quiz.status)

        sort_order = (
            payload.sort_order
            if payload.sort_order is not None
            else self._sections.next_sort_order(quiz_id)
        )
        self._ensure_sort_order_available(quiz_id, sort_order)

        section = self._sections.create(
            quiz_id=quiz_id,
            name=payload.name,
            sort_order=sort_order,
        )
        self._demote_ready_if_needed(quiz)
        self._session.commit()
        self._session.refresh(section)
        return section

    def list(self, quiz_id: UUID, *, owner_id: UUID | None = None) -> tuple[list[Section], int]:
        self._require_parent_quiz(quiz_id, owner_id=owner_id)
        items = self._sections.list_for_quiz(quiz_id)
        return items, len(items)

    def get(
        self,
        quiz_id: UUID,
        section_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> Section:
        self._require_parent_quiz(quiz_id, owner_id=owner_id)
        section = self._sections.get_for_quiz(quiz_id, section_id)
        if section is None:
            raise NotFoundError("SECTION_NOT_FOUND", "Section not found")
        return section

    def update(
        self,
        quiz_id: UUID,
        section_id: UUID,
        payload: SectionUpdateRequest,
        *,
        owner_id: UUID | None = None,
    ) -> Section:
        quiz = self._require_parent_quiz(quiz_id, owner_id=owner_id)
        self._ensure_quiz_mutable(quiz.status)
        section = self.get(quiz_id, section_id, owner_id=owner_id)

        if payload.name is not None:
            section.name = payload.name
        if payload.sort_order is not None and payload.sort_order != section.sort_order:
            self._ensure_sort_order_available(
                quiz_id,
                payload.sort_order,
                exclude_section_id=section.id,
            )
            section.sort_order = payload.sort_order

        self._demote_ready_if_needed(quiz)
        self._sections.flush()
        self._session.commit()
        self._session.refresh(section)
        return section

    def delete(
        self,
        quiz_id: UUID,
        section_id: UUID,
        *,
        owner_id: UUID | None = None,
    ) -> None:
        quiz = self._require_parent_quiz(quiz_id, owner_id=owner_id)
        self._ensure_quiz_mutable(quiz.status)
        section = self.get(quiz_id, section_id, owner_id=owner_id)
        self._sections.delete(section)
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

    @staticmethod
    def _ensure_quiz_mutable(status: QuizStatus) -> None:
        if status == QuizStatus.IN_USE:
            raise ConflictError(
                "QUIZ_IN_USE",
                "Cannot modify sections of a quiz that is currently in use by a live room",
            )
        if status not in _MUTABLE_QUIZ_STATUSES:
            raise ValidationError(
                "QUIZ_NOT_EDITABLE",
                f"Cannot modify sections when quiz status is '{status.value}'",
            )

    def _ensure_sort_order_available(
        self,
        quiz_id: UUID,
        sort_order: int,
        *,
        exclude_section_id: UUID | None = None,
    ) -> None:
        if self._sections.sort_order_taken(
            quiz_id,
            sort_order,
            exclude_section_id=exclude_section_id,
        ):
            raise ConflictError(
                "DUPLICATE_SORT_ORDER",
                f"Sort order {sort_order} is already used by another section in this quiz",
            )

    @staticmethod
    def _demote_ready_if_needed(quiz) -> None:
        # Content change invalidates Ready until full validation passes again.
        if quiz.status == QuizStatus.READY:
            quiz.status = QuizStatus.DRAFT
