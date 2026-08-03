"""Pydantic schemas for AI quiz generation APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    AiDifficulty,
    AiGenerationMode,
    AiJobStatus,
    AiQuestionKind,
    AiSourceKind,
)


class AiGenerateDocumentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, max_length=255)
    language: str = Field(default="en", max_length=16)
    question_count: int = Field(
        default=12,
        ge=1,
        le=100,
        serialization_alias="questionCount",
        validation_alias=AliasChoices("questionCount", "question_count"),
    )
    difficulty: AiDifficulty = AiDifficulty.MIXED
    question_kinds: list[AiQuestionKind] = Field(
        default_factory=lambda: [AiQuestionKind.MCQ],
        serialization_alias="questionKinds",
        validation_alias=AliasChoices("questionKinds", "question_kinds"),
    )


class AiGenerateTopicRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    topic: str = Field(min_length=2, max_length=500)
    title: str | None = Field(default=None, max_length=255)
    language: str = Field(default="en", max_length=16)
    question_count: int = Field(
        default=12,
        ge=1,
        le=100,
        serialization_alias="questionCount",
        validation_alias=AliasChoices("questionCount", "question_count"),
    )
    difficulty: AiDifficulty = AiDifficulty.MIXED
    question_kinds: list[AiQuestionKind] = Field(
        default_factory=lambda: [AiQuestionKind.MCQ],
        serialization_alias="questionKinds",
        validation_alias=AliasChoices("questionKinds", "question_kinds"),
    )

    @field_validator("topic")
    @classmethod
    def strip_topic(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Topic is required")
        return cleaned


class AiOptionData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: str
    is_correct: bool = Field(
        default=False,
        serialization_alias="isCorrect",
        validation_alias=AliasChoices("isCorrect", "is_correct"),
    )


class AiQuestionPatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prompt_text: str | None = Field(
        default=None,
        serialization_alias="promptText",
        validation_alias=AliasChoices("promptText", "prompt_text"),
    )
    explanation: str | None = None
    difficulty: AiDifficulty | None = None
    kind: AiQuestionKind | None = None
    topic_label: str | None = Field(
        default=None,
        serialization_alias="topicLabel",
        validation_alias=AliasChoices("topicLabel", "topic_label"),
    )
    estimated_time_seconds: int | None = Field(
        default=None,
        ge=5,
        le=300,
        serialization_alias="estimatedTimeSeconds",
        validation_alias=AliasChoices("estimatedTimeSeconds", "estimated_time_seconds"),
    )
    options: list[AiOptionData] | None = None


class AiSourceFileData(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    original_filename: str = Field(serialization_alias="originalFilename")
    mime_type: str = Field(serialization_alias="mimeType")
    file_size: int = Field(serialization_alias="fileSize")
    extractor: str | None = None


class AiSourceReferenceData(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    kind: AiSourceKind
    title: str
    locator: str
    publisher: str | None = None


class AiGeneratedQuestionData(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    kind: AiQuestionKind
    prompt_text: str = Field(serialization_alias="promptText")
    explanation: str | None = None
    difficulty: AiDifficulty
    topic_label: str | None = Field(default=None, serialization_alias="topicLabel")
    estimated_time_seconds: int = Field(serialization_alias="estimatedTimeSeconds")
    options: list[dict[str, Any]] = Field(default_factory=list)
    source_locator: str | None = Field(default=None, serialization_alias="sourceLocator")
    sort_order: int = Field(serialization_alias="sortOrder")


class AiGeneratedSectionData(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    name: str
    summary: str | None = None
    sort_order: int = Field(serialization_alias="sortOrder")
    concepts: list[Any] = Field(default_factory=list)
    questions: list[AiGeneratedQuestionData] = Field(default_factory=list)


class AiJobData(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    mode: AiGenerationMode
    status: AiJobStatus
    progress_percent: int = Field(serialization_alias="progressPercent")
    progress_message: str | None = Field(default=None, serialization_alias="progressMessage")
    error_code: str | None = Field(default=None, serialization_alias="errorCode")
    error_message: str | None = Field(default=None, serialization_alias="errorMessage")
    topic: str | None = None
    title: str | None = None
    language: str
    question_count: int = Field(serialization_alias="questionCount")
    difficulty: AiDifficulty
    question_kinds: list[str] = Field(default_factory=list, serialization_alias="questionKinds")
    result_quiz_id: UUID | None = Field(default=None, serialization_alias="resultQuizId")
    source_files: list[AiSourceFileData] = Field(default_factory=list, serialization_alias="sourceFiles")
    sources: list[AiSourceReferenceData] = Field(default_factory=list)
    sections: list[AiGeneratedSectionData] = Field(default_factory=list)
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    started_at: datetime | None = Field(default=None, serialization_alias="startedAt")
    completed_at: datetime | None = Field(default=None, serialization_alias="completedAt")


class AiSaveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    job_id: UUID = Field(
        serialization_alias="jobId",
        validation_alias=AliasChoices("jobId", "job_id"),
    )


class AiSaveResultData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    quiz_id: UUID = Field(serialization_alias="quizId")
    job_id: UUID = Field(serialization_alias="jobId")


class AiJobListData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[AiJobData]
