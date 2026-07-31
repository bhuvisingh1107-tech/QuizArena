"""Quiz CRUD business logic (API_SPEC.md §8, SYSTEM_ARCHITECTURE.md §8)."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.enums import QuizStatus
from app.models.quiz import Quiz
from app.models.quiz_config import QuizConfig
from app.repositories.quiz_repository import QuizRepository
from app.schemas.quiz import QuizConfigData, QuizCreateRequest, QuizUpdateRequest

# States that may be edited (architecture §8.3 Edit).
_EDITABLE_STATUSES = {QuizStatus.DRAFT, QuizStatus.READY}

# States that may be soft-deleted (architecture §8.3 Delete).
_DELETABLE_STATUSES = {QuizStatus.DRAFT, QuizStatus.READY, QuizStatus.ARCHIVED}


class QuizService:
    """Quiz library create / list / get / update / delete."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._quizzes = QuizRepository(session)

    def create(self, payload: QuizCreateRequest) -> Quiz:
        config_data = payload.config or QuizConfigData()
        config = self._build_config(config_data)
        quiz = self._quizzes.create(
            title=payload.title,
            description=payload.description,
            config=config,
        )
        self._session.commit()
        self._session.refresh(quiz)
        return quiz

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: QuizStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[Quiz], int]:
        items, total = self._quizzes.list(
            offset=offset,
            limit=limit,
            status=status,
            search=search,
            include_deleted=False,
            include_archived=False,
        )
        return items, total

    def get(self, quiz_id: UUID) -> Quiz:
        quiz = self._quizzes.get_by_id(quiz_id, include_deleted=False)
        if quiz is None:
            # Distinguish unknown vs soft-deleted for clearer 404
            deleted = self._quizzes.get_by_id(quiz_id, include_deleted=True)
            if deleted is not None and deleted.status == QuizStatus.DELETED:
                raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")
            raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")
        return quiz

    def update(self, quiz_id: UUID, payload: QuizUpdateRequest) -> Quiz:
        quiz = self.get(quiz_id)

        if quiz.status == QuizStatus.IN_USE:
            raise ConflictError(
                "QUIZ_IN_USE",
                "Cannot edit a quiz that is currently in use by a live room",
            )
        if quiz.status not in _EDITABLE_STATUSES:
            raise ValidationError(
                "QUIZ_NOT_EDITABLE",
                f"Quiz in status '{quiz.status.value}' cannot be edited",
            )

        if payload.title is not None:
            quiz.title = payload.title
        if payload.description is not None:
            quiz.description = payload.description
        if payload.config is not None:
            self._apply_config(quiz, payload.config)

        # Architecture §8.3: re-validate on save; Ready → Draft if validation fails.
        # Full Ready checklist needs sections/questions (not in this module).
        # Without content, a Ready quiz cannot remain Ready after edit.
        if quiz.status == QuizStatus.READY and not self._passes_ready_gate(quiz):
            quiz.status = QuizStatus.DRAFT

        self._quizzes.flush()
        self._session.commit()
        self._session.refresh(quiz)
        return quiz

    def delete(self, quiz_id: UUID, *, hard: bool = False) -> Quiz | None:
        """Soft-delete (status=Deleted) or hard-delete. Blocked when InUse."""
        quiz = self._quizzes.get_by_id(quiz_id, include_deleted=True)
        if quiz is None:
            raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")

        if quiz.status == QuizStatus.IN_USE:
            raise ConflictError(
                "QUIZ_IN_USE",
                "Cannot delete a quiz that is currently in use by a live room",
            )

        if quiz.status == QuizStatus.DELETED and not hard:
            raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")

        if quiz.status not in _DELETABLE_STATUSES and quiz.status != QuizStatus.DELETED:
            raise ValidationError(
                "QUIZ_NOT_DELETABLE",
                f"Quiz in status '{quiz.status.value}' cannot be deleted",
            )

        if hard:
            self._quizzes.delete(quiz)
            self._session.commit()
            return None

        quiz.status = QuizStatus.DELETED
        self._quizzes.flush()
        self._session.commit()
        self._session.refresh(quiz)
        return quiz

    @staticmethod
    def _build_config(data: QuizConfigData) -> QuizConfig:
        return QuizConfig(
            question_advance_mode=data.question_advance_mode,
            answer_reveal_behavior=data.answer_reveal_behavior,
            time_bonus_enabled=data.time_bonus_enabled,
            time_bonus_max_points=data.time_bonus_max_points,
            streak_bonus_enabled=data.streak_bonus_enabled,
            streak_bonus_rules=data.streak_bonus_rules,
            question_order_shuffle=data.question_order_shuffle,
            answer_option_shuffle=data.answer_option_shuffle,
        )

    @staticmethod
    def _apply_config(quiz: Quiz, data: QuizConfigData) -> None:
        if quiz.config is None:
            quiz.config = QuizService._build_config(data)
            return
        quiz.config.question_advance_mode = data.question_advance_mode
        quiz.config.answer_reveal_behavior = data.answer_reveal_behavior
        quiz.config.time_bonus_enabled = data.time_bonus_enabled
        quiz.config.time_bonus_max_points = data.time_bonus_max_points
        quiz.config.streak_bonus_enabled = data.streak_bonus_enabled
        quiz.config.streak_bonus_rules = data.streak_bonus_rules
        quiz.config.question_order_shuffle = data.question_order_shuffle
        quiz.config.answer_option_shuffle = data.answer_option_shuffle

    @staticmethod
    def _passes_ready_gate(quiz: Quiz) -> bool:
        """Subset of Ready checklist relevant without section/question APIs.

        Full checklist (sections, questions, options) is enforced when those
        modules land. For now: non-empty title + config present.
        """
        if not quiz.title or not quiz.title.strip():
            return False
        if quiz.config is None:
            return False
        # Without at least one section, Ready cannot be maintained.
        if not quiz.sections:
            return False
        return True
