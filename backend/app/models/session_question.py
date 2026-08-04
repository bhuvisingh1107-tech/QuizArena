"""Session question snapshot (DATABASE_SCHEMA.md §7.3)."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, CreatedAtMixin, str_enum
from app.models.enums import QuestionType, SessionQuestionState

if TYPE_CHECKING:
    from app.models.live_room import LiveRoom
    from app.models.media_file import MediaFile
    from app.models.response import Response
    from app.models.session_option import SessionOption
    from app.models.session_section import SessionSection


class SessionQuestion(Base, CreatedAtMixin):
    """Immutable snapshot of a question for a live room session."""

    __tablename__ = "session_questions"
    __table_args__ = (
        UniqueConstraint(
            "live_room_id",
            "sort_order",
            name="uq_session_questions_live_room_id_sort_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    live_room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("live_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_section_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("session_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_question_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
    )
    question_type: Mapped[QuestionType] = mapped_column(
        str_enum(QuestionType, length=16),
        nullable=False,
    )
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_file_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    base_points: Mapped[int] = mapped_column(Integer, nullable=False)
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allow_multiple_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[SessionQuestionState] = mapped_column(
        str_enum(SessionQuestionState, length=16),
        nullable=False,
        default=SessionQuestionState.PENDING,
        server_default=SessionQuestionState.PENDING.value,
    )
    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Server clock when question:started was emitted (audit / response-time anchor).
    broadcast_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    live_room: Mapped["LiveRoom"] = relationship("LiveRoom", back_populates="session_questions")
    session_section: Mapped["SessionSection"] = relationship(
        "SessionSection",
        back_populates="session_questions",
    )
    media_file: Mapped[Optional["MediaFile"]] = relationship("MediaFile")
    options: Mapped[list["SessionOption"]] = relationship(
        "SessionOption",
        back_populates="session_question",
        cascade="all, delete-orphan",
        order_by="SessionOption.sort_order",
    )
    responses: Mapped[list["Response"]] = relationship(
        "Response",
        back_populates="session_question",
        cascade="all, delete-orphan",
    )
