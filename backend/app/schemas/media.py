"""Media upload / metadata request and response schemas (API_SPEC.md §10)."""

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.models.enums import MediaCategory


class MediaAttachRequest(BaseModel):
    """Attach an uploaded media file to a question."""

    model_config = ConfigDict(populate_by_name=True)

    quiz_id: UUID = Field(
        serialization_alias="quizId",
        validation_alias=AliasChoices("quizId", "quiz_id"),
    )
    section_id: UUID = Field(
        serialization_alias="sectionId",
        validation_alias=AliasChoices("sectionId", "section_id"),
    )
    question_id: UUID = Field(
        serialization_alias="questionId",
        validation_alias=AliasChoices("questionId", "question_id"),
    )


class MediaResponseData(BaseModel):
    """Media file metadata + public reference URL."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    category: MediaCategory
    mime_type: str = Field(serialization_alias="mimeType")
    file_size: int = Field(serialization_alias="fileSize")
    original_filename: str | None = Field(
        default=None,
        serialization_alias="originalFilename",
    )
    quiz_id: UUID | None = Field(default=None, serialization_alias="quizId")
    url: str
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class MediaListData(BaseModel):
    """Media files scoped to a quiz (for builder picker)."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[MediaResponseData]
    total: int


class MediaDeleteData(BaseModel):
    """Delete acknowledgement."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    deleted: bool = True


class MediaAttachData(BaseModel):
    """Attach acknowledgement with updated question media reference."""

    model_config = ConfigDict(populate_by_name=True)

    media_id: UUID = Field(serialization_alias="mediaId")
    question_id: UUID = Field(serialization_alias="questionId")
    media_file_id: UUID = Field(serialization_alias="mediaFileId")
