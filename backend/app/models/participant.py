"""Participant model within a live room (DATABASE_SCHEMA.md §7.4)."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import ConnectionStatus, ParticipantState

if TYPE_CHECKING:
    from app.models.live_room import LiveRoom
    from app.models.response import Response


class Participant(Base, TimestampMixin):
    """Player within a live room, identified by display name and email."""

    __tablename__ = "participants"
    __table_args__ = (
        UniqueConstraint(
            "live_room_id",
            "display_name",
            name="uq_participants_live_room_id_display_name",
        ),
        UniqueConstraint(
            "live_room_id",
            "email",
            name="uq_participants_live_room_id_email",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    live_room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("live_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    session_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    state: Mapped[ParticipantState] = mapped_column(
        str_enum(ParticipantState, length=16),
        nullable=False,
        default=ParticipantState.JOINING,
        server_default=ParticipantState.JOINING.value,
    )
    connection_status: Mapped[ConnectionStatus] = mapped_column(
        str_enum(ConnectionStatus, length=16),
        nullable=False,
        default=ConnectionStatus.CONNECTED,
        server_default=ConnectionStatus.CONNECTED.value,
    )
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_incorrect: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unanswered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    live_room: Mapped["LiveRoom"] = relationship("LiveRoom", back_populates="participants")
    responses: Mapped[list["Response"]] = relationship(
        "Response",
        back_populates="participant",
        cascade="all, delete-orphan",
    )
