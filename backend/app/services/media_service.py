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
from app.schemas.media import MediaAttachRequest
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
    ) -> MediaFile:
        if category == MediaCategory.QUIZ_BRANDING:
            if quiz_id is None:
                raise ValidationError(
                    "QUIZ_ID_REQUIRED",
                    "quizId is required when uploading quiz branding media",
                )
            quiz = self._quizzes.get_by_id(quiz_id, include_deleted=False)
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
            quiz_id=quiz_id if category == MediaCategory.QUIZ_BRANDING else None,
        )
        self._session.commit()
        self._session.refresh(media)
        return media

    def get(self, media_id: UUID) -> MediaFile:
        media = self._media.get_by_id(media_id)
        if media is None:
            raise NotFoundError("MEDIA_NOT_FOUND", "Media file not found")
        return media

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

        quiz = self._quizzes.get_by_id(payload.quiz_id, include_deleted=False)
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
            raise ValidationError(
                "MEDIA_TYPE_MISMATCH",
                f"Media category '{media.category.value}' is not valid for "
                f"question type '{question.question_type.value}'",
            )

        previous_media_id = question.media_file_id
        question.media_file_id = media.id
        if quiz.status == QuizStatus.READY:
            quiz.status = QuizStatus.DRAFT
        self._questions.flush()
        self._session.commit()

        if previous_media_id is not None and previous_media_id != media.id:
            self._orphan_delete_if_unused(previous_media_id)

        return media, question.id

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
