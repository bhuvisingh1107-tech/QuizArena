"""Quiz CRUD business logic (API_SPEC.md §8, SYSTEM_ARCHITECTURE.md §8)."""

from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.enums import QuestionType, QuizStatus
from app.models.quiz import Quiz
from app.models.quiz_config import QuizConfig
from app.models.section import Section
from app.repositories.quiz_repository import QuizRepository
from app.schemas.quiz import QuizConfigData, QuizCreateRequest, QuizUpdateRequest

# States that may be edited (architecture §8.3 Edit).
_EDITABLE_STATUSES = {QuizStatus.DRAFT, QuizStatus.READY}

# States that may be soft-deleted (architecture §8.3 Delete).
_DELETABLE_STATUSES = {QuizStatus.DRAFT, QuizStatus.READY, QuizStatus.ARCHIVED}

_MAX_QUESTIONS = 100
_MIN_OPTIONS = 2
_MAX_OPTIONS = 6


class QuizService:
    """Quiz library create / list / get / update / delete / validate / archive."""

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
            from sqlalchemy import select

            from app.models.live_room import LiveRoom

            has_rooms = self._session.scalar(
                select(LiveRoom.id).where(LiveRoom.quiz_id == quiz.id).limit(1)
            )
            if has_rooms is not None:
                raise ConflictError(
                    "QUIZ_HAS_ROOMS",
                    "Cannot permanently delete a quiz that still has live room history. "
                    "Soft-delete instead, or delete closed rooms first.",
                )
            self._quizzes.delete(quiz)
            self._session.commit()
            return None

        quiz.status = QuizStatus.DELETED
        self._quizzes.flush()
        self._session.commit()
        self._session.refresh(quiz)
        return quiz

    def validate(self, quiz_id: UUID) -> Quiz:
        """Run Ready checklist and promote Draft → Ready (API_SPEC.md §8 Validate)."""
        quiz = self.get_with_content_loaded(quiz_id)

        if quiz.status == QuizStatus.IN_USE:
            raise ConflictError(
                "QUIZ_IN_USE",
                "Cannot validate a quiz that is currently in use by a live room",
            )
        if quiz.status == QuizStatus.ARCHIVED:
            raise ValidationError(
                "QUIZ_ARCHIVED",
                "Restore the quiz before validating",
            )
        if quiz.status not in {QuizStatus.DRAFT, QuizStatus.READY}:
            raise ValidationError(
                "QUIZ_NOT_VALIDATABLE",
                f"Quiz in status '{quiz.status.value}' cannot be validated",
            )

        errors = self._collect_ready_errors(quiz)
        if errors:
            raise ValidationError(
                "QUIZ_NOT_READY",
                "Quiz does not meet the Ready checklist",
                details=errors,
            )

        quiz.status = QuizStatus.READY
        self._quizzes.flush()
        self._session.commit()
        self._session.refresh(quiz)
        from app.core.audit import audit

        audit("quiz.publish", quiz_id=str(quiz.id), title=quiz.title, status=quiz.status.value)
        return quiz

    def archive(self, quiz_id: UUID) -> Quiz:
        quiz = self.get(quiz_id)
        if quiz.status != QuizStatus.READY:
            raise ValidationError(
                "QUIZ_NOT_ARCHIVABLE",
                "Only Ready quizzes can be archived",
            )
        quiz.status = QuizStatus.ARCHIVED
        self._quizzes.flush()
        self._session.commit()
        self._session.refresh(quiz)
        return quiz

    def restore(self, quiz_id: UUID) -> Quiz:
        quiz = self._quizzes.get_by_id(quiz_id, include_deleted=False)
        if quiz is None:
            raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")
        if quiz.status != QuizStatus.ARCHIVED:
            raise ValidationError(
                "QUIZ_NOT_RESTORABLE",
                "Only Archived quizzes can be restored",
            )
        loaded = self.get_with_content_loaded(quiz_id)
        errors = self._collect_ready_errors(loaded)
        if errors:
            quiz.status = QuizStatus.DRAFT
            self._quizzes.flush()
            self._session.commit()
            self._session.refresh(quiz)
            raise ValidationError(
                "QUIZ_NOT_READY",
                "Quiz no longer meets the Ready checklist; restored as Draft",
                details=errors,
            )
        quiz.status = QuizStatus.READY
        self._quizzes.flush()
        self._session.commit()
        self._session.refresh(quiz)
        return quiz

    def get_with_content_loaded(self, quiz_id: UUID) -> Quiz:
        from app.models.question import Question
        from sqlalchemy import select

        stmt = (
            select(Quiz)
            .where(Quiz.id == quiz_id)
            .options(
                selectinload(Quiz.config),
                selectinload(Quiz.sections)
                .selectinload(Section.questions)
                .selectinload(Question.options),
            )
        )
        quiz = self._session.scalar(stmt)
        if quiz is None or quiz.status == QuizStatus.DELETED:
            raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")
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

    def _passes_ready_gate(self, quiz: Quiz) -> bool:
        try:
            loaded = self.get_with_content_loaded(quiz.id)
        except NotFoundError:
            return False
        return not self._collect_ready_errors(loaded)

    @staticmethod
    def _collect_ready_errors(quiz: Quiz) -> list[dict]:
        errors: list[dict] = []

        if not quiz.title or not quiz.title.strip():
            errors.append({"field": "title", "message": "Quiz title is required"})

        if quiz.config is None:
            errors.append({"field": "config", "message": "Quiz configuration is required"})

        sections = list(quiz.sections or [])
        if not sections:
            errors.append({"field": "sections", "message": "At least one section is required"})
            return errors

        total_questions = 0
        for section in sections:
            questions = list(section.questions or [])
            if not questions:
                errors.append(
                    {
                        "field": f"sections.{section.id}",
                        "message": f'Section "{section.name}" must contain at least one question',
                    }
                )
                continue

            for question in questions:
                total_questions += 1
                q_path = f"questions.{question.id}"
                if not question.prompt_text or not question.prompt_text.strip():
                    errors.append({"field": f"{q_path}.promptText", "message": "Question text is required"})
                if question.base_points < 1:
                    errors.append({"field": f"{q_path}.basePoints", "message": "Base points must be ≥ 1"})

                options = list(question.options or [])
                if len(options) < _MIN_OPTIONS or len(options) > _MAX_OPTIONS:
                    errors.append(
                        {
                            "field": f"{q_path}.options",
                            "message": f"Each question needs {_MIN_OPTIONS}–{_MAX_OPTIONS} options",
                        }
                    )
                elif not any(opt.is_correct for opt in options):
                    errors.append(
                        {
                            "field": f"{q_path}.options",
                            "message": "At least one option must be marked correct",
                        }
                    )

                if question.question_type in {QuestionType.IMAGE, QuestionType.AUDIO}:
                    if question.media_file_id is None:
                        errors.append(
                            {
                                "field": f"{q_path}.mediaFileId",
                                "message": f"{question.question_type.value} questions require attached media",
                            }
                        )

        if total_questions > _MAX_QUESTIONS:
            errors.append(
                {
                    "field": "questions",
                    "message": f"A quiz may contain at most {_MAX_QUESTIONS} questions",
                }
            )
        elif total_questions == 0:
            errors.append({"field": "questions", "message": "At least one question is required"})

        return errors
