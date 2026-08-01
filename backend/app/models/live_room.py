"""Live room session model (DATABASE_SCHEMA.md §7.1)."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import LobbySubState, RoomState

if TYPE_CHECKING:
    from app.models.participant import Participant
    from app.models.quiz import Quiz
    from app.models.room_ban import RoomBan
    from app.models.room_config import RoomConfig
    from app.models.session_question import SessionQuestion
    from app.models.session_section import SessionSection


class LiveRoom(Base, TimestampMixin):
    """Runtime session instance created from a Ready quiz."""

    __tablename__ = "live_rooms"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    quiz_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    state: Mapped[RoomState] = mapped_column(
        str_enum(RoomState, length=16),
        nullable=False,
        default=RoomState.SETUP,
        server_default=RoomState.SETUP.value,
        index=True,
    )
    lobby_sub_state: Mapped[LobbySubState | None] = mapped_column(
        str_enum(LobbySubState, length=16),
        nullable=True,
    )
    room_code: Mapped[str] = mapped_column(String(6), unique=True, nullable=False, index=True)
    secret_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    quiz_title_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    current_question_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    codes_expired: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pause_accumulated_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="live_rooms")
    config: Mapped[Optional["RoomConfig"]] = relationship(
        "RoomConfig",
        back_populates="live_room",
        uselist=False,
        cascade="all, delete-orphan",
    )
    session_sections: Mapped[list["SessionSection"]] = relationship(
        "SessionSection",
        back_populates="live_room",
        cascade="all, delete-orphan",
        order_by="SessionSection.sort_order",
    )
    session_questions: Mapped[list["SessionQuestion"]] = relationship(
        "SessionQuestion",
        back_populates="live_room",
        cascade="all, delete-orphan",
        order_by="SessionQuestion.sort_order",
    )
    participants: Mapped[list["Participant"]] = relationship(
        "Participant",
        back_populates="live_room",
        cascade="all, delete-orphan",
    )
    bans: Mapped[list["RoomBan"]] = relationship(
        "RoomBan",
        back_populates="live_room",
        cascade="all, delete-orphan",
    )
