"""Media file metadata model (DATABASE_SCHEMA.md §8.1)."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import MediaCategory

if TYPE_CHECKING:
    from app.models.quiz import Quiz


class MediaFile(Base, TimestampMixin):
    """Stored file metadata; bytes live on the storage backend."""

    __tablename__ = "media_files"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    category: Mapped[MediaCategory] = mapped_column(
        str_enum(MediaCategory, length=32),
        nullable=False,
        index=True,
    )
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quiz_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    quiz: Mapped[Optional["Quiz"]] = relationship(
        "Quiz",
        back_populates="branding_files",
        foreign_keys=[quiz_id],
    )
