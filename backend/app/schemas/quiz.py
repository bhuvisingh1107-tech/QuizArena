"""Quiz request/response schemas (API_SPEC.md §8)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic import AliasChoices

from app.models.enums import AnswerRevealBehavior, QuestionAdvanceMode, QuizStatus


def _alias(*names: str) -> AliasChoices:
    return AliasChoices(*names)


class QuizConfigData(BaseModel):
    """Quiz scoring and behavior settings."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    question_advance_mode: QuestionAdvanceMode = Field(
        default=QuestionAdvanceMode.MANUAL,
        serialization_alias="questionAdvanceMode",
        validation_alias=_alias("questionAdvanceMode", "question_advance_mode"),
    )
    answer_reveal_behavior: AnswerRevealBehavior = Field(
        default=AnswerRevealBehavior.AFTER_EACH,
        serialization_alias="answerRevealBehavior",
        validation_alias=_alias("answerRevealBehavior", "answer_reveal_behavior"),
    )
    time_bonus_enabled: bool = Field(
        default=False,
        serialization_alias="timeBonusEnabled",
        validation_alias=_alias("timeBonusEnabled", "time_bonus_enabled"),
    )
    time_bonus_max_points: int = Field(
        default=0,
        ge=0,
        serialization_alias="timeBonusMaxPoints",
        validation_alias=_alias("timeBonusMaxPoints", "time_bonus_max_points"),
    )
    streak_bonus_enabled: bool = Field(
        default=False,
        serialization_alias="streakBonusEnabled",
        validation_alias=_alias("streakBonusEnabled", "streak_bonus_enabled"),
    )
    streak_bonus_rules: dict[str, Any] | None = Field(
        default=None,
        serialization_alias="streakBonusRules",
        validation_alias=_alias("streakBonusRules", "streak_bonus_rules"),
    )
    question_order_shuffle: bool = Field(
        default=False,
        serialization_alias="questionOrderShuffle",
        validation_alias=_alias("questionOrderShuffle", "question_order_shuffle"),
    )
    answer_option_shuffle: bool = Field(
        default=False,
        serialization_alias="answerOptionShuffle",
        validation_alias=_alias("answerOptionShuffle", "answer_option_shuffle"),
    )


class QuizCreateRequest(BaseModel):
    """POST /quizzes body — creates a Draft quiz with default config."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    config: QuizConfigData | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Title must not be blank")
        return cleaned


class QuizUpdateRequest(BaseModel):
    """PATCH /quizzes/{id} body — partial update."""

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    config: QuizConfigData | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Title must not be blank")
        return cleaned


class QuizResponseData(BaseModel):
    """Quiz detail / list item payload."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    title: str
    description: str | None = None
    status: QuizStatus
    branding_media_file_id: UUID | None = Field(
        default=None,
        serialization_alias="brandingMediaFileId",
    )
    config: QuizConfigData | None = None
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class QuizListData(BaseModel):
    """Paginated quiz library payload."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[QuizResponseData]
    total: int
    offset: int
    limit: int


class QuizDeleteData(BaseModel):
    """Delete acknowledgement."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    deleted: bool = True
    hard: bool = False
    status: QuizStatus | None = None
