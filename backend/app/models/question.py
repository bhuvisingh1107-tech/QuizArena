"""Question model within a section (DATABASE_SCHEMA.md §6.3)."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import QuestionType

if TYPE_CHECKING:
    from app.models.answer_option import AnswerOption
    from app.models.media_file import MediaFile
    from app.models.section import Section


class Question(Base, TimestampMixin):
    """Ordered question within a quiz section."""

    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("section_id", "sort_order", name="uq_questions_section_id_sort_order"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    section_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_type: Mapped[QuestionType] = mapped_column(
        str_enum(QuestionType, length=16),
        nullable=False,
    )
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_file_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("media_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    base_points: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allow_multiple_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    section: Mapped["Section"] = relationship("Section", back_populates="questions")
    media_file: Mapped[Optional["MediaFile"]] = relationship("MediaFile")
    options: Mapped[list["AnswerOption"]] = relationship(
        "AnswerOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="AnswerOption.sort_order",
    )
