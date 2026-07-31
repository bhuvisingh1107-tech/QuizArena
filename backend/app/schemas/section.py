"""Section request/response schemas (API_SPEC.md §9)."""

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class SectionCreateRequest(BaseModel):
    """POST /quizzes/{quiz_id}/sections body."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=255)
    sort_order: int | None = Field(
        default=None,
        ge=0,
        serialization_alias="sortOrder",
        validation_alias=AliasChoices("sortOrder", "sort_order"),
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Section name must not be blank")
        return cleaned


class SectionUpdateRequest(BaseModel):
    """PATCH /quizzes/{quiz_id}/sections/{section_id} body."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    sort_order: int | None = Field(
        default=None,
        ge=0,
        serialization_alias="sortOrder",
        validation_alias=AliasChoices("sortOrder", "sort_order"),
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Section name must not be blank")
        return cleaned


class SectionResponseData(BaseModel):
    """Section payload."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    quiz_id: UUID = Field(serialization_alias="quizId")
    name: str
    sort_order: int = Field(serialization_alias="sortOrder")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class SectionListData(BaseModel):
    """Ordered sections for a quiz."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[SectionResponseData]
    total: int


class SectionDeleteData(BaseModel):
    """Delete acknowledgement."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    deleted: bool = True
