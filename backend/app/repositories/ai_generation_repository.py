"""Persistence helpers for AI generation jobs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.ai_generation import (
    AiDocumentChunk,
    AiGeneratedQuestion,
    AiGeneratedSection,
    AiGenerationJob,
    AiSourceFile,
    AiSourceReference,
)


class AiGenerationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entity: object) -> None:
        self._session.add(entity)

    def commit(self) -> None:
        self._session.commit()

    def flush(self) -> None:
        self._session.flush()

    def get_job(self, job_id: UUID, *, owner_id: UUID | None = None) -> AiGenerationJob | None:
        stmt = (
            select(AiGenerationJob)
            .where(AiGenerationJob.id == job_id)
            .options(
                selectinload(AiGenerationJob.source_files),
                selectinload(AiGenerationJob.sources),
                selectinload(AiGenerationJob.sections).selectinload(AiGeneratedSection.questions),
            )
        )
        if owner_id is not None:
            stmt = stmt.where(AiGenerationJob.owner_id == owner_id)
        return self._session.scalar(stmt)

    def list_jobs(self, *, owner_id: UUID, limit: int = 20) -> list[AiGenerationJob]:
        stmt = (
            select(AiGenerationJob)
            .where(AiGenerationJob.owner_id == owner_id)
            .order_by(AiGenerationJob.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())

    def get_question(
        self,
        question_id: UUID,
        *,
        owner_id: UUID,
    ) -> AiGeneratedQuestion | None:
        stmt = (
            select(AiGeneratedQuestion)
            .join(AiGenerationJob, AiGeneratedQuestion.job_id == AiGenerationJob.id)
            .where(
                AiGeneratedQuestion.id == question_id,
                AiGenerationJob.owner_id == owner_id,
            )
            .options(selectinload(AiGeneratedQuestion.section))
        )
        return self._session.scalar(stmt)

    def get_section(
        self,
        section_id: UUID,
        *,
        owner_id: UUID,
    ) -> AiGeneratedSection | None:
        stmt = (
            select(AiGeneratedSection)
            .join(AiGenerationJob, AiGeneratedSection.job_id == AiGenerationJob.id)
            .where(
                AiGeneratedSection.id == section_id,
                AiGenerationJob.owner_id == owner_id,
            )
            .options(selectinload(AiGeneratedSection.questions))
        )
        return self._session.scalar(stmt)

    def delete_section_questions(self, section: AiGeneratedSection) -> None:
        for question in list(section.questions):
            self._session.delete(question)
        self._session.flush()

    def clear_job_content(self, job: AiGenerationJob) -> None:
        for section in list(job.sections):
            self._session.delete(section)
        for chunk in list(job.chunks):
            self._session.delete(chunk)
        for source in list(job.sources):
            if source.kind != AiSourceKind.UPLOADED_FILE:
                self._session.delete(source)
        self._session.flush()
