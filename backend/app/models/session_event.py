"""Append-only live session timeline events (for export / audit)."""

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.models.base import Base, CreatedAtMixin

if TYPE_CHECKING:
    from app.models.live_room import LiveRoom


class SessionEvent(Base, CreatedAtMixin):
    """Chronological event during a live room session."""

    __tablename__ = "session_events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    live_room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("live_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    live_room: Mapped["LiveRoom"] = relationship("LiveRoom", back_populates="session_events")
