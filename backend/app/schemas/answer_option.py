"""Answer option request/response schemas (API_SPEC.md §9)."""

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class AnswerOptionCreateRequest(BaseModel):
    """POST .../questions/{question_id}/options body."""

    model_config = ConfigDict(populate_by_name=True)

    text: str = Field(min_length=1, max_length=500)
    is_correct: bool = Field(
        default=False,
        serialization_alias="isCorrect",
        validation_alias=AliasChoices("isCorrect", "is_correct"),
    )
    sort_order: int | None = Field(
        default=None,
        ge=0,
        serialization_alias="sortOrder",
        validation_alias=AliasChoices("sortOrder", "sort_order"),
    )

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Option text must not be blank")
        return cleaned


class AnswerOptionUpdateRequest(BaseModel):
    """PATCH .../options/{option_id} body."""

    model_config = ConfigDict(populate_by_name=True)

    text: str | None = Field(default=None, min_length=1, max_length=500)
    is_correct: bool | None = Field(
        default=None,
        serialization_alias="isCorrect",
        validation_alias=AliasChoices("isCorrect", "is_correct"),
    )
    sort_order: int | None = Field(
        default=None,
        ge=0,
        serialization_alias="sortOrder",
        validation_alias=AliasChoices("sortOrder", "sort_order"),
    )

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Option text must not be blank")
        return cleaned


class AnswerOptionResponseData(BaseModel):
    """Answer option payload."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    question_id: UUID = Field(serialization_alias="questionId")
    text: str
    is_correct: bool = Field(serialization_alias="isCorrect")
    sort_order: int = Field(serialization_alias="sortOrder")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class AnswerOptionListData(BaseModel):
    """Ordered options for a question."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[AnswerOptionResponseData]
    total: int


class AnswerOptionDeleteData(BaseModel):
    """Delete acknowledgement."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    deleted: bool = True
