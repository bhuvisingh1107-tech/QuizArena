"""Quiz template model (DATABASE_SCHEMA.md §6.1)."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import QuizStatus

if TYPE_CHECKING:
    from app.models.live_room import LiveRoom
    from app.models.media_file import MediaFile
    from app.models.quiz_config import QuizConfig
    from app.models.section import Section


class Quiz(Base, TimestampMixin):
    """Durable quiz template owned by a host account."""

    __tablename__ = "quizzes"
    __table_args__ = (
        Index("ix_quizzes_status_title", "status", "title"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admins.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[QuizStatus] = mapped_column(
        str_enum(QuizStatus, length=16),
        nullable=False,
        default=QuizStatus.DRAFT,
        server_default=QuizStatus.DRAFT.value,
        index=True,
    )
    branding_media_file_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "media_files.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_quizzes_branding_media_file_id_media_files",
        ),
        nullable=True,
    )

    branding_media_file: Mapped[Optional["MediaFile"]] = relationship(
        "MediaFile",
        foreign_keys=[branding_media_file_id],
    )
    config: Mapped["QuizConfig"] = relationship(
        "QuizConfig",
        back_populates="quiz",
        uselist=False,
        cascade="all, delete-orphan",
    )
    sections: Mapped[list["Section"]] = relationship(
        "Section",
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="Section.sort_order",
    )
    branding_files: Mapped[list["MediaFile"]] = relationship(
        "MediaFile",
        back_populates="quiz",
        foreign_keys="MediaFile.quiz_id",
    )
    live_rooms: Mapped[list["LiveRoom"]] = relationship(
        "LiveRoom",
        back_populates="quiz",
    )
