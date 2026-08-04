"""Media upload, metadata, delete, and question attach (API_SPEC.md §10)."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.enums import MediaCategory, QuestionType, QuizStatus
from app.models.media_file import MediaFile
from app.repositories.media_repository import MediaRepository
from app.repositories.question_repository import QuestionRepository
from app.repositories.quiz_repository import QuizRepository
from app.repositories.section_repository import SectionRepository
from app.schemas.media import MediaAttachRequest, MediaQuizScopeRequest
from app.services.file_storage_service import FileStorageService

_MUTABLE_QUIZ_STATUSES = {QuizStatus.DRAFT, QuizStatus.READY}

_QUESTION_TYPE_CATEGORIES: dict[QuestionType, set[MediaCategory]] = {
    QuestionType.IMAGE: {MediaCategory.QUESTION_IMAGE},
    QuestionType.AUDIO: {MediaCategory.QUESTION_AUDIO},
    QuestionType.BUZZER: {MediaCategory.QUESTION_IMAGE, MediaCategory.QUESTION_AUDIO},
    QuestionType.TEXT: set(),
}

_PUBLIC_URL_TEMPLATE = "/api/v1/media/{media_id}/content"


class MediaService:
    """MediaFile metadata lifecycle + storage orchestration."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        storage: FileStorageService | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage or FileStorageService(settings)
        self._media = MediaRepository(session)
        self._quizzes = QuizRepository(session)
        self._sections = SectionRepository(session)
        self._questions = QuestionRepository(session)

    @staticmethod
    def public_url(media_id: UUID) -> str:
        return _PUBLIC_URL_TEMPLATE.format(media_id=media_id)

    def upload(
        self,
        *,
        data: bytes,
        category: MediaCategory,
        original_filename: str | None,
        quiz_id: UUID | None = None,
        declared_content_type: str | None = None,
        owner_id: UUID | None = None,
    ) -> MediaFile:
        if category == MediaCategory.QUIZ_BRANDING:
            if quiz_id is None:
                raise ValidationError(
                    "QUIZ_ID_REQUIRED",
                    "quizId is required when uploading quiz branding media",
                )
            quiz = self._quizzes.get_by_id(
                quiz_id,
                include_deleted=False,
                owner_id=owner_id,
            )
            if quiz is None:
                raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")

        stored = self._storage.upload(
            data,
            category,
            quiz_id=str(quiz_id) if quiz_id else None,
            declared_content_type=declared_content_type,
        )

        media = self._media.create(
            storage_key=stored.storage_key,
            category=category,
            mime_type=stored.mime_type,
            file_size=stored.file_size,
            original_filename=original_filename,
            quiz_id=quiz_id,
        )
        self._session.commit()
        self._session.refresh(media)
        return media

    def get(self, media_id: UUID) -> MediaFile:
        media = self._media.get_by_id(media_id)
        if media is None:
            raise NotFoundError("MEDIA_NOT_FOUND", "Media file not found")
        return media

    def list_for_quiz(
        self,
        quiz_id: UUID,
        *,
        category: MediaCategory | None = None,
        owner_id: UUID | None = None,
    ) -> list[MediaFile]:
        quiz = self._quizzes.get_by_id(
            quiz_id,
            include_deleted=False,
            owner_id=owner_id,
        )
        if quiz is None:
            raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")
        return self._media.list_for_quiz(quiz_id, category=category)

    def read_content(self, media_id: UUID) -> tuple[MediaFile, bytes]:
        media = self.get(media_id)
        data = self._storage.read(media.storage_key)
        return media, data

    def delete(self, media_id: UUID) -> None:
        media = self.get(media_id)
        if self._media.is_referenced(media_id):
            raise ConflictError(
                "MEDIA_IN_USE",
                "Media file is still referenced by a question or branding asset",
            )
        storage_key = media.storage_key
        self._media.delete(media)
        self._session.commit()
        self._storage.delete(storage_key)

    def attach_to_question(
        self,
        media_id: UUID,
        payload: MediaAttachRequest,
        *,
        owner_id: UUID | None = None,
    ) -> tuple[MediaFile, UUID]:
        """Attach media to a question; replace prior attachment and orphan-delete if unused."""
        media = self.get(media_id)
        if media.category not in {
            MediaCategory.QUESTION_IMAGE,
            MediaCategory.QUESTION_AUDIO,
        }:
            raise ValidationError(
                "INVALID_MEDIA_CATEGORY",
                "Only question image or audio media can be attached to a question",
            )

        quiz = self._quizzes.get_by_id(
            payload.quiz_id,
            include_deleted=False,
            owner_id=owner_id,
        )
        if quiz is None:
            raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")
        self._ensure_quiz_mutable(quiz.status)

        section = self._sections.get_for_quiz(payload.quiz_id, payload.section_id)
        if section is None:
            raise NotFoundError("SECTION_NOT_FOUND", "Section not found")

        question = self._questions.get_for_section(payload.section_id, payload.question_id)
        if question is None:
            raise NotFoundError("QUESTION_NOT_FOUND", "Question not found")

        allowed = _QUESTION_TYPE_CATEGORIES.get(question.question_type, set())
        if media.category not in allowed:
            # Promote Text questions to the matching media type so the builder can
            # attach image/audio without a separate type PATCH.
            if question.question_type == QuestionType.TEXT:
                self._promote_question_type_for_media(question, media.category)
            else:
                raise ValidationError(
                    "MEDIA_TYPE_MISMATCH",
                    f"Media category '{media.category.value}' is not valid for "
                    f"question type '{question.question_type.value}'",
                )
        if media.quiz_id is None:
            media.quiz_id = payload.quiz_id

        previous_media_id = question.media_file_id
        question.media_file_id = media.id
        if quiz.status == QuizStatus.READY:
            quiz.status = QuizStatus.DRAFT
        self._questions.flush()
        self._session.commit()

        if previous_media_id is not None and previous_media_id != media.id:
            self._orphan_delete_if_unused(previous_media_id)

        return media, question.id

    def apply_to_all_questions(
        self,
        media_id: UUID,
        payload: MediaQuizScopeRequest,
        *,
        owner_id: UUID | None = None,
    ) -> tuple[MediaFile, list[UUID], int]:
        """
        Point every compatible question in the quiz at this media file.

        Uploads are never duplicated — only ``media_file_id`` references are updated.
        Incompatible question types (e.g. Audio when attaching an image) are skipped.
        """
        media = self.get(media_id)
        if media.category not in {
            MediaCategory.QUESTION_IMAGE,
            MediaCategory.QUESTION_AUDIO,
        }:
            raise ValidationError(
                "INVALID_MEDIA_CATEGORY",
                "Only question image or audio media can be applied to questions",
            )

        quiz = self._quizzes.get_by_id(
            payload.quiz_id,
            include_deleted=False,
            owner_id=owner_id,
        )
        if quiz is None:
            raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")
        self._ensure_quiz_mutable(quiz.status)

        if media.quiz_id is None:
            media.quiz_id = payload.quiz_id
        elif media.quiz_id != payload.quiz_id:
            raise ValidationError(
                "MEDIA_QUIZ_MISMATCH",
                "Media belongs to a different quiz",
            )

        questions = self._questions.list_for_quiz(payload.quiz_id)
        if not questions:
            raise ValidationError(
                "NO_QUESTIONS",
                "This quiz has no questions to attach media to",
            )

        previous_ids: set[UUID] = set()
        updated_ids: list[UUID] = []
        skipped = 0

        for question in questions:
            if not self._can_attach_category(question.question_type, media.category):
                skipped += 1
                continue
            self._promote_question_type_for_media(question, media.category)
            previous = question.media_file_id
            if previous is not None and previous != media.id:
                previous_ids.add(previous)
            question.media_file_id = media.id
            updated_ids.append(question.id)

        if not updated_ids:
            raise ValidationError(
                "NO_COMPATIBLE_QUESTIONS",
                "No questions in this quiz can accept this media type",
            )

        if quiz.status == QuizStatus.READY:
            quiz.status = QuizStatus.DRAFT
        self._questions.flush()
        self._session.commit()

        for previous_media_id in previous_ids:
            self._orphan_delete_if_unused(previous_media_id)

        return media, updated_ids, skipped

    def remove_from_all_questions(
        self,
        media_id: UUID,
        payload: MediaQuizScopeRequest,
        *,
        owner_id: UUID | None = None,
    ) -> int:
        """Clear ``media_file_id`` on every question in the quiz that references this media."""
        media = self.get(media_id)

        quiz = self._quizzes.get_by_id(
            payload.quiz_id,
            include_deleted=False,
            owner_id=owner_id,
        )
        if quiz is None:
            raise NotFoundError("QUIZ_NOT_FOUND", "Quiz not found")
        self._ensure_quiz_mutable(quiz.status)

        questions = self._questions.list_for_quiz(payload.quiz_id)
        cleared = 0
        for question in questions:
            if question.media_file_id == media.id:
                question.media_file_id = None
                cleared += 1

        if cleared == 0:
            return 0

        if quiz.status == QuizStatus.READY:
            quiz.status = QuizStatus.DRAFT
        self._questions.flush()
        self._session.commit()
        # Keep the media object — host may re-attach. Storage is not duplicated.
        return cleared

    @staticmethod
    def _can_attach_category(question_type: QuestionType, category: MediaCategory) -> bool:
        if question_type == QuestionType.TEXT:
            return category in {
                MediaCategory.QUESTION_IMAGE,
                MediaCategory.QUESTION_AUDIO,
            }
        allowed = _QUESTION_TYPE_CATEGORIES.get(question_type, set())
        return category in allowed

    @staticmethod
    def _promote_question_type_for_media(question, category: MediaCategory) -> None:
        if question.question_type != QuestionType.TEXT:
            return
        if category == MediaCategory.QUESTION_IMAGE:
            question.question_type = QuestionType.IMAGE
        elif category == MediaCategory.QUESTION_AUDIO:
            question.question_type = QuestionType.AUDIO

    def _orphan_delete_if_unused(self, media_id: UUID) -> None:
        media = self._media.get_by_id(media_id)
        if media is None:
            return
        if self._media.is_referenced(media_id):
            return
        storage_key = media.storage_key
        self._media.delete(media)
        self._session.commit()
        self._storage.delete(storage_key)

    @staticmethod
    def _ensure_quiz_mutable(status: QuizStatus) -> None:
        if status == QuizStatus.IN_USE:
            raise ConflictError(
                "QUIZ_IN_USE",
                "Cannot attach media to a quiz that is currently in use by a live room",
            )
        if status not in _MUTABLE_QUIZ_STATUSES:
            raise ValidationError(
                "QUIZ_NOT_EDITABLE",
                f"Cannot attach media when quiz status is '{status.value}'",
            )
