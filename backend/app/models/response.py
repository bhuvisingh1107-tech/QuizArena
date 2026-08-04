"""Participant response and score record (DATABASE_SCHEMA.md §7.5)."""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.models.base import Base, CreatedAtMixin

if TYPE_CHECKING:
    from app.models.participant import Participant
    from app.models.session_question import SessionQuestion


class Response(Base, CreatedAtMixin):
    """One response (and awarded points) per question per participant.

    Score components live on this row (conceptual Score Record under Response
    in DATABASE_SCHEMA.md §3).
    """

    __tablename__ = "responses"
    __table_args__ = (
        UniqueConstraint(
            "participant_id",
            "session_question_id",
            name="uq_responses_participant_id_session_question_id",
        ),
        Index("ix_responses_participant_id_session_question_id", "participant_id", "session_question_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    participant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("participants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_question_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("session_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    selected_option_ids: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_unanswered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    base_points_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    time_bonus_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streak_bonus_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_points_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="submitted")
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Leaderboard standing immediately before/after this answer was scored (reveal).
    rank_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    participant: Mapped["Participant"] = relationship("Participant", back_populates="responses")
    session_question: Mapped["SessionQuestion"] = relationship(
        "SessionQuestion",
        back_populates="responses",
    )
