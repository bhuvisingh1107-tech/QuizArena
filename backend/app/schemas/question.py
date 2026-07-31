"""Question request/response schemas (API_SPEC.md §9)."""

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.models.enums import QuestionType


class QuestionCreateRequest(BaseModel):
    """POST .../sections/{section_id}/questions body."""

    model_config = ConfigDict(populate_by_name=True)

    question_type: QuestionType = Field(
        serialization_alias="questionType",
        validation_alias=AliasChoices("questionType", "question_type"),
    )
    prompt_text: str = Field(
        min_length=1,
        serialization_alias="promptText",
        validation_alias=AliasChoices("promptText", "prompt_text"),
    )
    base_points: int = Field(
        default=1,
        ge=1,
        serialization_alias="basePoints",
        validation_alias=AliasChoices("basePoints", "base_points"),
    )
    time_limit_seconds: int | None = Field(
        default=None,
        ge=1,
        serialization_alias="timeLimitSeconds",
        validation_alias=AliasChoices("timeLimitSeconds", "time_limit_seconds"),
    )
    allow_multiple_correct: bool = Field(
        default=False,
        serialization_alias="allowMultipleCorrect",
        validation_alias=AliasChoices("allowMultipleCorrect", "allow_multiple_correct"),
    )
    sort_order: int | None = Field(
        default=None,
        ge=0,
        serialization_alias="sortOrder",
        validation_alias=AliasChoices("sortOrder", "sort_order"),
    )

    @field_validator("prompt_text")
    @classmethod
    def strip_prompt(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question text must not be blank")
        return cleaned


class QuestionUpdateRequest(BaseModel):
    """PATCH .../questions/{question_id} body."""

    model_config = ConfigDict(populate_by_name=True)

    question_type: QuestionType | None = Field(
        default=None,
        serialization_alias="questionType",
        validation_alias=AliasChoices("questionType", "question_type"),
    )
    prompt_text: str | None = Field(
        default=None,
        min_length=1,
        serialization_alias="promptText",
        validation_alias=AliasChoices("promptText", "prompt_text"),
    )
    base_points: int | None = Field(
        default=None,
        ge=1,
        serialization_alias="basePoints",
        validation_alias=AliasChoices("basePoints", "base_points"),
    )
    time_limit_seconds: int | None = Field(
        default=None,
        ge=1,
        serialization_alias="timeLimitSeconds",
        validation_alias=AliasChoices("timeLimitSeconds", "time_limit_seconds"),
    )
    allow_multiple_correct: bool | None = Field(
        default=None,
        serialization_alias="allowMultipleCorrect",
        validation_alias=AliasChoices("allowMultipleCorrect", "allow_multiple_correct"),
    )
    sort_order: int | None = Field(
        default=None,
        ge=0,
        serialization_alias="sortOrder",
        validation_alias=AliasChoices("sortOrder", "sort_order"),
    )

    @field_validator("prompt_text")
    @classmethod
    def strip_prompt(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question text must not be blank")
        return cleaned


class QuestionResponseData(BaseModel):
    """Question payload."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    section_id: UUID = Field(serialization_alias="sectionId")
    question_type: QuestionType = Field(serialization_alias="questionType")
    prompt_text: str | None = Field(default=None, serialization_alias="promptText")
    media_file_id: UUID | None = Field(default=None, serialization_alias="mediaFileId")
    base_points: int = Field(serialization_alias="basePoints")
    time_limit_seconds: int | None = Field(default=None, serialization_alias="timeLimitSeconds")
    allow_multiple_correct: bool = Field(serialization_alias="allowMultipleCorrect")
    sort_order: int = Field(serialization_alias="sortOrder")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class QuestionListData(BaseModel):
    """Ordered questions for a section."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[QuestionResponseData]
    total: int


class QuestionDeleteData(BaseModel):
    """Delete acknowledgement."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    deleted: bool = True
