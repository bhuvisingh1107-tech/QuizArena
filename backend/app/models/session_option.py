"""Session answer option snapshot (DATABASE_SCHEMA.md §7.3)."""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, CreatedAtMixin

if TYPE_CHECKING:
    from app.models.session_question import SessionQuestion


class SessionOption(Base, CreatedAtMixin):
    """Immutable snapshot of an answer option for a session question."""

    __tablename__ = "session_options"
    __table_args__ = (
        UniqueConstraint(
            "session_question_id",
            "sort_order",
            name="uq_session_options_session_question_id_sort_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    session_question_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("session_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_option_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("answer_options.id", ondelete="SET NULL"),
        nullable=True,
    )
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    session_question: Mapped["SessionQuestion"] = relationship(
        "SessionQuestion",
        back_populates="options",
    )
