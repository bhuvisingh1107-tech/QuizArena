"""Platform settings model (DATABASE_SCHEMA.md §9)."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.media_file import MediaFile


class PlatformSettings(Base, TimestampMixin):
    """Platform-wide configuration and branding defaults."""

    __tablename__ = "platform_settings"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    platform_name: Mapped[str] = mapped_column(String(128), nullable=False, default="QuizArena")
    logo_media_file_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_files.id", ondelete="SET NULL"),
        nullable=True,
    )

    logo_media_file: Mapped[Optional["MediaFile"]] = relationship("MediaFile")
