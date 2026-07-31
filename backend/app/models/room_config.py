"""Room configuration snapshot (DATABASE_SCHEMA.md §7.2)."""

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.models.base import Base, CreatedAtMixin, str_enum
from app.models.enums import AnswerRevealBehavior, QuestionAdvanceMode

if TYPE_CHECKING:
    from app.models.live_room import LiveRoom


class RoomConfig(Base, CreatedAtMixin):
    """Immutable snapshot of QuizConfig at live room creation."""

    __tablename__ = "room_configs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    live_room_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("live_rooms.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    question_advance_mode: Mapped[QuestionAdvanceMode] = mapped_column(
        str_enum(QuestionAdvanceMode, length=16),
        nullable=False,
    )
    answer_reveal_behavior: Mapped[AnswerRevealBehavior] = mapped_column(
        str_enum(AnswerRevealBehavior, length=16),
        nullable=False,
    )
    time_bonus_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    time_bonus_max_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streak_bonus_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    streak_bonus_rules: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    question_order_shuffle: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    answer_option_shuffle: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    live_room: Mapped["LiveRoom"] = relationship("LiveRoom", back_populates="config")
