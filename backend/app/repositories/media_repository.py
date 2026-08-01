"""Media file metadata data access (DATABASE_SCHEMA.md §8.1)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import MediaCategory
from app.models.media_file import MediaFile
from app.models.platform_settings import PlatformSettings
from app.models.question import Question
from app.models.quiz import Quiz


class MediaRepository:
    """Repository for MediaFile metadata records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        storage_key: str,
        category: MediaCategory,
        mime_type: str,
        file_size: int,
        original_filename: str | None,
        quiz_id: UUID | None,
    ) -> MediaFile:
        media = MediaFile(
            storage_key=storage_key,
            category=category,
            mime_type=mime_type,
            file_size=file_size,
            original_filename=original_filename,
            quiz_id=quiz_id,
        )
        self._session.add(media)
        self._session.flush()
        return media

    def get_by_id(self, media_id: UUID) -> MediaFile | None:
        return self._session.get(MediaFile, media_id)

    def list_for_quiz(
        self,
        quiz_id: UUID,
        *,
        category: MediaCategory | None = None,
    ) -> list[MediaFile]:
        stmt = select(MediaFile).where(MediaFile.quiz_id == quiz_id)
        if category is not None:
            stmt = stmt.where(MediaFile.category == category)
        stmt = stmt.order_by(MediaFile.created_at.desc())
        return list(self._session.scalars(stmt).all())

    def delete(self, media: MediaFile) -> None:
        self._session.delete(media)
        self._session.flush()

    def flush(self) -> None:
        self._session.flush()

    def count_question_references(self, media_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Question)
            .where(Question.media_file_id == media_id)
        )
        return int(self._session.scalar(stmt) or 0)

    def count_quiz_branding_references(self, media_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Quiz)
            .where(Quiz.branding_media_file_id == media_id)
        )
        return int(self._session.scalar(stmt) or 0)

    def count_platform_branding_references(self, media_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(PlatformSettings)
            .where(PlatformSettings.logo_media_file_id == media_id)
        )
        return int(self._session.scalar(stmt) or 0)

    def is_referenced(self, media_id: UUID) -> bool:
        return (
            self.count_question_references(media_id) > 0
            or self.count_quiz_branding_references(media_id) > 0
            or self.count_platform_branding_references(media_id) > 0
        )

    def list_question_ids_using(self, media_id: UUID) -> list[UUID]:
        stmt = select(Question.id).where(Question.media_file_id == media_id)
        return list(self._session.scalars(stmt).all())
