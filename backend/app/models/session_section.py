"""Session section snapshot (DATABASE_SCHEMA.md §3, §7.3)."""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, CreatedAtMixin

if TYPE_CHECKING:
    from app.models.live_room import LiveRoom
    from app.models.session_question import SessionQuestion


class SessionSection(Base, CreatedAtMixin):
    """Immutable snapshot of a quiz section for a live room."""

    __tablename__ = "session_sections"
    __table_args__ = (
        UniqueConstraint(
            "live_room_id",
            "sort_order",
            name="uq_session_sections_live_room_id_sort_order",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    live_room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("live_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_section_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    live_room: Mapped["LiveRoom"] = relationship("LiveRoom", back_populates="session_sections")
    session_questions: Mapped[list["SessionQuestion"]] = relationship(
        "SessionQuestion",
        back_populates="session_section",
        cascade="all, delete-orphan",
        order_by="SessionQuestion.sort_order",
    )
