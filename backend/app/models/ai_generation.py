"""AI quiz generation persistence (jobs, sources, chunks, draft questions)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import (
    AiDifficulty,
    AiGenerationMode,
    AiJobStatus,
    AiQuestionKind,
    AiSourceKind,
)

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.quiz import Quiz

# JSON that works on SQLite (JSON) and Postgres (JSONB when available).
JsonType = JSON().with_variant(JSONB(), "postgresql")


class AiGenerationJob(Base, TimestampMixin):
    """Async generation job owned by a host."""

    __tablename__ = "ai_generation_jobs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mode: Mapped[AiGenerationMode] = mapped_column(
        str_enum(AiGenerationMode, length=16),
        nullable=False,
    )
    status: Mapped[AiJobStatus] = mapped_column(
        str_enum(AiJobStatus, length=16),
        nullable=False,
        default=AiJobStatus.QUEUED,
        index=True,
    )
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    topic: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    difficulty: Mapped[AiDifficulty] = mapped_column(
        str_enum(AiDifficulty, length=16),
        nullable=False,
        default=AiDifficulty.MIXED,
    )
    question_kinds: Mapped[list[Any]] = mapped_column(JsonType, nullable=False, default=list)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)

    result_quiz_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("quizzes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped["Admin"] = relationship("Admin")
    result_quiz: Mapped[Optional["Quiz"]] = relationship("Quiz")
    source_files: Mapped[list["AiSourceFile"]] = relationship(
        "AiSourceFile",
        back_populates="job",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[list["AiDocumentChunk"]] = relationship(
        "AiDocumentChunk",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="AiDocumentChunk.chunk_index",
    )
    sections: Mapped[list["AiGeneratedSection"]] = relationship(
        "AiGeneratedSection",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="AiGeneratedSection.sort_order",
    )
    sources: Mapped[list["AiSourceReference"]] = relationship(
        "AiSourceReference",
        back_populates="job",
        cascade="all, delete-orphan",
    )


class AiSourceFile(Base, TimestampMixin):
    """Uploaded study material for a generation job."""

    __tablename__ = "ai_source_files"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_generation_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extractor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extracted_char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extracted_text_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    job: Mapped["AiGenerationJob"] = relationship("AiGenerationJob", back_populates="source_files")


class AiDocumentChunk(Base, TimestampMixin):
    """Normalized text chunk + embedding metadata (not stored on quiz tables)."""

    __tablename__ = "ai_document_chunks"
    __table_args__ = (
        UniqueConstraint("job_id", "chunk_index", name="uq_ai_document_chunks_job_chunk"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_generation_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_file_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_source_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    section_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Portable embedding storage (JSON float array). Postgres may add pgvector later.
    embedding_json: Mapped[list[Any] | None] = mapped_column(JsonType, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    job: Mapped["AiGenerationJob"] = relationship("AiGenerationJob", back_populates="chunks")


class AiGeneratedSection(Base, TimestampMixin):
    """Detected / planned section before save into template quizzes."""

    __tablename__ = "ai_generated_sections"
    __table_args__ = (
        UniqueConstraint("job_id", "sort_order", name="uq_ai_generated_sections_job_sort"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_generation_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    concepts_json: Mapped[list[Any]] = mapped_column(JsonType, nullable=False, default=list)

    job: Mapped["AiGenerationJob"] = relationship("AiGenerationJob", back_populates="sections")
    questions: Mapped[list["AiGeneratedQuestion"]] = relationship(
        "AiGeneratedQuestion",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="AiGeneratedQuestion.sort_order",
    )


class AiGeneratedQuestion(Base, TimestampMixin):
    """Draft AI question awaiting host review before save."""

    __tablename__ = "ai_generated_questions"
    __table_args__ = (
        UniqueConstraint(
            "section_id",
            "sort_order",
            name="uq_ai_generated_questions_section_sort",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_generation_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_generated_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[AiQuestionKind] = mapped_column(
        str_enum(AiQuestionKind, length=32),
        nullable=False,
        default=AiQuestionKind.MCQ,
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[AiDifficulty] = mapped_column(
        str_enum(AiDifficulty, length=16),
        nullable=False,
        default=AiDifficulty.MEDIUM,
    )
    topic_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    estimated_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    options_json: Mapped[list[Any]] = mapped_column(JsonType, nullable=False, default=list)
    source_locator: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    section: Mapped["AiGeneratedSection"] = relationship(
        "AiGeneratedSection",
        back_populates="questions",
    )


class AiSourceReference(Base, TimestampMixin):
    """Attribution for uploaded files or trusted web sources."""

    __tablename__ = "ai_source_references"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_generation_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[AiSourceKind] = mapped_column(
        str_enum(AiSourceKind, length=32),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    locator: Mapped[str] = mapped_column(String(1024), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)

    job: Mapped["AiGenerationJob"] = relationship("AiGenerationJob", back_populates="sources")
