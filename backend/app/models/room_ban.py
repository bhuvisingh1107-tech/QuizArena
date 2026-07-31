"""Per-room email ban list (DATABASE_SCHEMA.md §7.6)."""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.models.base import Base, CreatedAtMixin

if TYPE_CHECKING:
    from app.models.live_room import LiveRoom


class RoomBan(Base, CreatedAtMixin):
    """Banned participant email for a specific live room."""

    __tablename__ = "room_bans"
    __table_args__ = (
        UniqueConstraint("live_room_id", "email", name="uq_room_bans_live_room_id_email"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    live_room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("live_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)

    live_room: Mapped["LiveRoom"] = relationship("LiveRoom", back_populates="bans")
