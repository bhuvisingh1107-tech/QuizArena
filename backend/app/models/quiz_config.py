"""Quiz configuration model (DATABASE_SCHEMA.md §6.5)."""

from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import AnswerRevealBehavior, QuestionAdvanceMode

if TYPE_CHECKING:
    from app.models.quiz import Quiz


class QuizConfig(Base, TimestampMixin):
    """1:1 scoring and behavior settings for a quiz template."""

    __tablename__ = "quiz_configs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    quiz_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    question_advance_mode: Mapped[QuestionAdvanceMode] = mapped_column(
        str_enum(QuestionAdvanceMode, length=16),
        nullable=False,
        default=QuestionAdvanceMode.MANUAL,
        server_default=QuestionAdvanceMode.MANUAL.value,
    )
    answer_reveal_behavior: Mapped[AnswerRevealBehavior] = mapped_column(
        str_enum(AnswerRevealBehavior, length=16),
        nullable=False,
        default=AnswerRevealBehavior.AFTER_EACH,
        server_default=AnswerRevealBehavior.AFTER_EACH.value,
    )
    time_bonus_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    time_bonus_max_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streak_bonus_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    streak_bonus_rules: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    question_order_shuffle: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    answer_option_shuffle: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="config")
