"""Orchestrates document/topic → structured sections → draft questions."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.ai_generation import (
    AiDocumentChunk,
    AiGeneratedQuestion,
    AiGeneratedSection,
    AiGenerationJob,
    AiSourceFile,
    AiSourceReference,
)
from app.models.enums import (
    AiDifficulty,
    AiGenerationMode,
    AiJobStatus,
    AiQuestionKind,
    AiSourceKind,
)
from app.repositories.ai_generation_repository import AiGenerationRepository
from app.services.ai.chunking import chunk_text, normalize_text
from app.services.ai.extractors import extract_text
from app.services.ai.prompts import (
    QUESTIONS_SYSTEM,
    QUESTIONS_USER,
    REGENERATE_QUESTION_SYSTEM,
    STRUCTURE_SYSTEM,
    STRUCTURE_USER,
    TOPIC_OUTLINE_SYSTEM,
    TOPIC_OUTLINE_USER,
    load_prompt,
)
from app.services.ai.provider import ChatMessage, get_ai_provider, render_template
from app.services.ai.trusted_sources import trusted_source_seeds
from app.storage.local import LocalStorageBackend


class AiGenerationService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._repo = AiGenerationRepository(session)
        self._storage_root = Path(self._settings.storage_path).resolve()
        self._storage_root.mkdir(parents=True, exist_ok=True)
        (self._storage_root / "ai-sources").mkdir(parents=True, exist_ok=True)
        self._provider = get_ai_provider(self._settings)

    # ── Job creation ───────────────────────────────────────────────────────

    def create_document_job(
        self,
        *,
        owner_id: UUID,
        title: str | None,
        language: str,
        question_count: int,
        difficulty: AiDifficulty,
        question_kinds: list[AiQuestionKind],
    ) -> AiGenerationJob:
        self._validate_settings(question_count, question_kinds)
        job = AiGenerationJob(
            id=uuid4(),
            owner_id=owner_id,
            mode=AiGenerationMode.DOCUMENT,
            status=AiJobStatus.QUEUED,
            title=(title or "").strip() or None,
            language=language or "en",
            question_count=question_count,
            difficulty=difficulty,
            question_kinds=[k.value for k in question_kinds],
            settings_json={"provider": self._provider.name},
            progress_percent=0,
            progress_message="Waiting for upload",
        )
        self._repo.add(job)
        self._repo.commit()
        return job

    def create_topic_job(
        self,
        *,
        owner_id: UUID,
        topic: str,
        title: str | None,
        language: str,
        question_count: int,
        difficulty: AiDifficulty,
        question_kinds: list[AiQuestionKind],
    ) -> AiGenerationJob:
        topic_clean = topic.strip()
        if len(topic_clean) < 2:
            raise ValidationError("VALIDATION_ERROR", "Topic is required")
        self._validate_settings(question_count, question_kinds)
        job = AiGenerationJob(
            id=uuid4(),
            owner_id=owner_id,
            mode=AiGenerationMode.TOPIC,
            status=AiJobStatus.QUEUED,
            topic=topic_clean,
            title=(title or topic_clean).strip()[:255],
            language=language or "en",
            question_count=question_count,
            difficulty=difficulty,
            question_kinds=[k.value for k in question_kinds],
            settings_json={"provider": self._provider.name},
            progress_percent=0,
            progress_message="Queued",
        )
        self._repo.add(job)
        self._repo.commit()
        return job

    def attach_upload(
        self,
        job_id: UUID,
        *,
        owner_id: UUID,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> AiSourceFile:
        job = self._require_job(job_id, owner_id=owner_id)
        if job.mode != AiGenerationMode.DOCUMENT:
            raise ValidationError("VALIDATION_ERROR", "Uploads are only valid for document jobs")
        if job.status not in {AiJobStatus.QUEUED, AiJobStatus.UPLOADING, AiJobStatus.FAILED}:
            raise ValidationError("INVALID_STATE", "Cannot upload to a job already processing")
        if len(data) > self._settings.ai_max_source_bytes:
            raise ValidationError(
                "FILE_TOO_LARGE",
                f"Source file exceeds {self._settings.ai_max_source_bytes} bytes",
            )
        suffix = Path(filename).suffix.lower()
        key = f"ai-sources/{job.id}/{uuid4().hex}{suffix}"
        absolute = self._storage_root / key
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_bytes(data)
        source = AiSourceFile(
            id=uuid4(),
            job_id=job.id,
            storage_key=key,
            original_filename=filename[:255],
            mime_type=content_type or "application/octet-stream",
            file_size=len(data),
        )
        job.status = AiJobStatus.UPLOADING
        job.progress_message = "File uploaded"
        job.progress_percent = 5
        self._repo.add(source)
        self._repo.add(
            AiSourceReference(
                id=uuid4(),
                job_id=job.id,
                kind=AiSourceKind.UPLOADED_FILE,
                title=filename[:255],
                locator=key,
                publisher=None,
                meta_json={"mimeType": content_type, "size": len(data)},
            )
        )
        self._repo.commit()
        return source

    def get_job(self, job_id: UUID, *, owner_id: UUID) -> AiGenerationJob:
        return self._require_job(job_id, owner_id=owner_id)

    def list_jobs(self, *, owner_id: UUID, limit: int = 20) -> list[AiGenerationJob]:
        return self._repo.list_jobs(owner_id=owner_id, limit=limit)

    def cancel_job(self, job_id: UUID, *, owner_id: UUID) -> AiGenerationJob:
        job = self._require_job(job_id, owner_id=owner_id)
        if job.status in {AiJobStatus.COMPLETED, AiJobStatus.CANCELLED}:
            return job
        job.status = AiJobStatus.CANCELLED
        job.progress_message = "Cancelled"
        job.completed_at = datetime.now(UTC)
        self._repo.commit()
        return job

    # ── Pipeline (called by worker) ────────────────────────────────────────

    def run_job(self, job_id: UUID) -> AiGenerationJob:
        job = self._repo.get_job(job_id)
        if job is None:
            raise NotFoundError("NOT_FOUND", "Generation job not found")
        if job.status == AiJobStatus.CANCELLED:
            return job

        job.started_at = datetime.now(UTC)
        try:
            if job.mode == AiGenerationMode.DOCUMENT:
                self._run_document(job)
            else:
                self._run_topic(job)
            job.status = AiJobStatus.COMPLETED
            job.progress_percent = 100
            job.progress_message = "Ready for review"
            job.completed_at = datetime.now(UTC)
            self._repo.commit()
        except Exception as exc:
            self._session.rollback()
            job = self._repo.get_job(job_id) or job
            job.status = AiJobStatus.FAILED
            job.error_code = getattr(exc, "code", None) or "AI_GENERATION_FAILED"
            job.error_message = str(getattr(exc, "message", None) or exc)[:2000]
            job.progress_message = "Failed"
            job.completed_at = datetime.now(UTC)
            self._repo.commit()
            raise
        return job

    def _run_document(self, job: AiGenerationJob) -> None:
        if not job.source_files:
            raise ValidationError("VALIDATION_ERROR", "Upload at least one source file")

        self._set_progress(job, 10, AiJobStatus.EXTRACTING, "Extracting text")
        combined: list[str] = []
        for source in job.source_files:
            absolute = self._storage_root / source.storage_key
            if not absolute.is_file():
                raise ValidationError(
                    "SOURCE_MISSING",
                    f"Stored file missing for {source.original_filename}",
                )
            result = extract_text(
                absolute,
                mime_type=source.mime_type,
                filename=source.original_filename,
            )
            text = normalize_text(result.text)
            if not text:
                raise ValidationError(
                    "EMPTY_EXTRACTION",
                    f"No text extracted from {source.original_filename}",
                )
            source.extractor = result.extractor
            source.extracted_char_count = len(text)
            combined.append(f"# Source: {source.original_filename}\n\n{text}")

        full_text = "\n\n".join(combined)
        self._set_progress(job, 25, AiJobStatus.EXTRACTING, "Chunking content")
        self._store_chunks(job, full_text)

        self._set_progress(job, 40, AiJobStatus.ANALYZING, "Detecting sections")
        outline = self._detect_structure(job, full_text)
        self._set_progress(job, 55, AiJobStatus.GENERATING, "Generating questions")
        self._generate_questions_for_outline(job, outline, full_text)

    def _run_topic(self, job: AiGenerationJob) -> None:
        assert job.topic
        self._set_progress(job, 15, AiJobStatus.ANALYZING, "Planning sections from topic")
        outline = self._topic_outline(job)

        for src in trusted_source_seeds(job.topic):
            self._repo.add(
                AiSourceReference(
                    id=uuid4(),
                    job_id=job.id,
                    kind=AiSourceKind.WEB_URL,
                    title=src["title"][:255],
                    locator=src["url"],
                    publisher=src.get("publisher"),
                    meta_json={},
                )
            )
        for item in outline.get("trustedSources") or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            self._repo.add(
                AiSourceReference(
                    id=uuid4(),
                    job_id=job.id,
                    kind=AiSourceKind.WEB_URL,
                    title=str(item.get("title") or url)[:255],
                    locator=url[:1024],
                    publisher=str(item.get("publisher") or "")[:255] or None,
                    meta_json={},
                )
            )

        # Topic mode uses outline summaries as synthetic source text.
        synthetic = "\n\n".join(
            f"## {s.get('name')}\n{s.get('summary', '')}\nConcepts: "
            f"{', '.join(s.get('concepts') or [])}"
            for s in outline.get("sections") or []
        )
        self._store_chunks(job, synthetic or job.topic)
        self._set_progress(job, 55, AiJobStatus.GENERATING, "Generating questions")
        self._generate_questions_for_outline(job, outline, synthetic or job.topic)

    def _store_chunks(self, job: AiGenerationJob, text: str) -> None:
        for existing in list(job.chunks):
            self._session.delete(existing)
        self._session.flush()
        chunks = chunk_text(text)
        embeddings = self._provider.embed([c.content for c in chunks]) if chunks else []
        for idx, chunk in enumerate(chunks):
            embedding = embeddings[idx] if idx < len(embeddings) else None
            self._repo.add(
                AiDocumentChunk(
                    id=uuid4(),
                    job_id=job.id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    token_estimate=chunk.token_estimate,
                    section_hint=chunk.section_hint,
                    embedding_json=embedding,
                    embedding_model=self._settings.ai_embedding_model if embedding else None,
                )
            )
        self._repo.flush()

    def _detect_structure(self, job: AiGenerationJob, source_text: str) -> dict[str, Any]:
        system = load_prompt(STRUCTURE_SYSTEM)
        user = render_template(
            load_prompt(STRUCTURE_USER),
            language=job.language,
            title_hint=job.title or "none",
            source_text=source_text[:24000],
        )
        return self._provider.chat_json(
            [ChatMessage("system", system), ChatMessage("user", user)],
        )

    def _topic_outline(self, job: AiGenerationJob) -> dict[str, Any]:
        system = load_prompt(TOPIC_OUTLINE_SYSTEM)
        user = render_template(
            load_prompt(TOPIC_OUTLINE_USER),
            topic=job.topic or "",
            language=job.language,
        )
        return self._provider.chat_json(
            [ChatMessage("system", system), ChatMessage("user", user)],
        )

    def _generate_questions_for_outline(
        self,
        job: AiGenerationJob,
        outline: dict[str, Any],
        source_text: str,
    ) -> None:
        sections_data = outline.get("sections") or []
        if not sections_data:
            raise ValidationError("AI_STRUCTURE_EMPTY", "AI did not detect any sections")

        if outline.get("title") and not job.title:
            job.title = str(outline["title"])[:255]

        # Clear previous drafts on regenerate-all.
        for section in list(job.sections):
            self._session.delete(section)
        self._session.flush()

        total_q = max(1, job.question_count)
        per = max(1, total_q // len(sections_data))
        remainder = total_q - per * len(sections_data)
        kinds = [str(k) for k in (job.question_kinds or ["mcq"])]

        created = 0
        for sort_order, raw in enumerate(sections_data):
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or f"Section {sort_order + 1}")[:255]
            section = AiGeneratedSection(
                id=uuid4(),
                job_id=job.id,
                name=name,
                summary=str(raw.get("summary") or "")[:4000] or None,
                sort_order=sort_order,
                concepts_json=list(raw.get("concepts") or []),
            )
            self._repo.add(section)
            self._repo.flush()

            count = per + (1 if sort_order < remainder else 0)
            questions = self._ask_questions(
                job=job,
                section_name=name,
                section_summary=section.summary or "",
                concepts=section.concepts_json,
                question_count=count,
                kinds=kinds,
                source_text=source_text,
            )
            for q_index, item in enumerate(questions):
                self._repo.add(self._question_from_payload(job, section, item, q_index))
                created += 1
            pct = 55 + int(40 * (sort_order + 1) / max(1, len(sections_data)))
            self._set_progress(
                job,
                min(95, pct),
                AiJobStatus.GENERATING,
                f"Generated section: {name}",
            )

        if created == 0:
            raise ValidationError("AI_GENERATION_EMPTY", "No questions were generated")

    def _ask_questions(
        self,
        *,
        job: AiGenerationJob,
        section_name: str,
        section_summary: str,
        concepts: list[Any],
        question_count: int,
        kinds: list[str],
        source_text: str,
    ) -> list[dict[str, Any]]:
        system = load_prompt(QUESTIONS_SYSTEM)
        user = render_template(
            load_prompt(QUESTIONS_USER),
            question_count=question_count,
            section_name=section_name,
            difficulty=job.difficulty.value,
            question_kinds=", ".join(kinds),
            language=job.language,
            section_summary=section_summary,
            concepts=", ".join(str(c) for c in concepts),
            source_text=source_text[:18000],
        )
        data = self._provider.chat_json(
            [ChatMessage("system", system), ChatMessage("user", user)],
            temperature=0.4,
        )
        questions = data.get("questions") or []
        return [q for q in questions if isinstance(q, dict)]

    def regenerate_question(
        self,
        question_id: UUID,
        *,
        owner_id: UUID,
    ) -> AiGeneratedQuestion:
        question = self._repo.get_question(question_id, owner_id=owner_id)
        if question is None:
            raise NotFoundError("NOT_FOUND", "Generated question not found")
        job = self._require_job(question.job_id, owner_id=owner_id)
        section = question.section
        system = load_prompt(REGENERATE_QUESTION_SYSTEM)
        user = (
            f"Regenerate a {question.kind.value} question about {section.name}.\n"
            f"Difficulty: {question.difficulty.value}\n"
            f"Language: {job.language}\n"
            f"Previous prompt: {question.prompt_text}"
        )
        data = self._provider.chat_json(
            [ChatMessage("system", system), ChatMessage("user", user)],
            temperature=0.5,
        )
        # Provider may return {question: {...}} or the object itself.
        payload = data.get("question") if isinstance(data.get("question"), dict) else data
        updated = self._question_from_payload(job, section, payload, question.sort_order)
        question.kind = updated.kind
        question.prompt_text = updated.prompt_text
        question.explanation = updated.explanation
        question.difficulty = updated.difficulty
        question.topic_label = updated.topic_label
        question.estimated_time_seconds = updated.estimated_time_seconds
        question.options_json = updated.options_json
        question.source_locator = updated.source_locator
        self._repo.commit()
        return question

    def regenerate_section(self, section_id: UUID, *, owner_id: UUID) -> AiGeneratedSection:
        section = self._repo.get_section(section_id, owner_id=owner_id)
        if section is None:
            raise NotFoundError("NOT_FOUND", "Generated section not found")
        job = self._require_job(section.job_id, owner_id=owner_id)
        source_text = "\n\n".join(c.content for c in job.chunks) or (job.topic or section.name)
        count = max(1, len(section.questions) or 3)
        kinds = [str(k) for k in (job.question_kinds or ["mcq"])]
        self._repo.delete_section_questions(section)
        questions = self._ask_questions(
            job=job,
            section_name=section.name,
            section_summary=section.summary or "",
            concepts=section.concepts_json,
            question_count=count,
            kinds=kinds,
            source_text=source_text,
        )
        for idx, item in enumerate(questions):
            self._repo.add(self._question_from_payload(job, section, item, idx))
        self._repo.commit()
        refreshed = self._repo.get_section(section_id, owner_id=owner_id)
        assert refreshed is not None
        return refreshed

    def queue_full_regeneration(self, job_id: UUID, *, owner_id: UUID) -> AiGenerationJob:
        """Clear draft output and mark the job queued for a full pipeline re-run."""
        job = self._require_job(job_id, owner_id=owner_id)
        if job.status in {
            AiJobStatus.QUEUED,
            AiJobStatus.UPLOADING,
            AiJobStatus.EXTRACTING,
            AiJobStatus.ANALYZING,
            AiJobStatus.GENERATING,
        }:
            raise ValidationError("VALIDATION_ERROR", "Job is already running")
        if job.mode == AiGenerationMode.DOCUMENT and not job.source_files:
            raise ValidationError("VALIDATION_ERROR", "Upload a source file before regenerating")
        if job.mode == AiGenerationMode.TOPIC and not (job.topic or "").strip():
            raise ValidationError("VALIDATION_ERROR", "Topic is required to regenerate")
        self._repo.clear_job_content(job)
        job.status = AiJobStatus.QUEUED
        job.progress_percent = 0
        job.progress_message = "Queued for regeneration"
        job.error_code = None
        job.error_message = None
        job.started_at = None
        job.completed_at = None
        job.result_quiz_id = None
        self._repo.commit()
        return job

    def update_question(
        self,
        question_id: UUID,
        *,
        owner_id: UUID,
        patch: dict[str, Any],
    ) -> AiGeneratedQuestion:
        question = self._repo.get_question(question_id, owner_id=owner_id)
        if question is None:
            raise NotFoundError("NOT_FOUND", "Generated question not found")
        if "promptText" in patch and patch["promptText"] is not None:
            question.prompt_text = str(patch["promptText"]).strip()
        if "explanation" in patch:
            question.explanation = (
                str(patch["explanation"]).strip() if patch["explanation"] is not None else None
            )
        if "difficulty" in patch and patch["difficulty"]:
            question.difficulty = AiDifficulty(str(patch["difficulty"]))
        if "topicLabel" in patch:
            question.topic_label = (
                str(patch["topicLabel"]).strip()[:255] if patch["topicLabel"] else None
            )
        if "estimatedTimeSeconds" in patch and patch["estimatedTimeSeconds"] is not None:
            question.estimated_time_seconds = int(patch["estimatedTimeSeconds"])
        if "options" in patch and isinstance(patch["options"], list):
            question.options_json = patch["options"]
        if "kind" in patch and patch["kind"]:
            question.kind = AiQuestionKind(str(patch["kind"]))
        self._repo.commit()
        return question

    def delete_question(self, question_id: UUID, *, owner_id: UUID) -> None:
        question = self._repo.get_question(question_id, owner_id=owner_id)
        if question is None:
            raise NotFoundError("NOT_FOUND", "Generated question not found")
        self._session.delete(question)
        self._repo.commit()

    # ── helpers ────────────────────────────────────────────────────────────

    def _question_from_payload(
        self,
        job: AiGenerationJob,
        section: AiGeneratedSection,
        payload: dict[str, Any],
        sort_order: int,
    ) -> AiGeneratedQuestion:
        kind_raw = str(payload.get("kind") or "mcq")
        try:
            kind = AiQuestionKind(kind_raw)
        except ValueError:
            kind = AiQuestionKind.MCQ
        diff_raw = str(payload.get("difficulty") or job.difficulty.value)
        if diff_raw == "mixed":
            diff_raw = "medium"
        try:
            difficulty = AiDifficulty(diff_raw)
        except ValueError:
            difficulty = AiDifficulty.MEDIUM
        options = payload.get("options") or []
        if not isinstance(options, list):
            options = []
        return AiGeneratedQuestion(
            id=uuid4(),
            job_id=job.id,
            section_id=section.id,
            kind=kind,
            prompt_text=str(payload.get("promptText") or payload.get("prompt_text") or "").strip()
            or f"Question about {section.name}",
            explanation=(
                str(payload.get("explanation")).strip()
                if payload.get("explanation") is not None
                else None
            ),
            difficulty=difficulty,
            topic_label=(
                str(payload.get("topicLabel") or payload.get("topic_label") or section.name)[:255]
            ),
            estimated_time_seconds=int(
                payload.get("estimatedTimeSeconds")
                or payload.get("estimated_time_seconds")
                or 20
            ),
            options_json=options,
            source_locator=(
                str(payload.get("sourceLocator") or payload.get("source_locator") or "")[:512]
                or None
            ),
            sort_order=sort_order,
        )

    def _set_progress(
        self,
        job: AiGenerationJob,
        percent: int,
        status: AiJobStatus,
        message: str,
    ) -> None:
        job.progress_percent = percent
        job.status = status
        job.progress_message = message
        self._repo.commit()

    def _require_job(self, job_id: UUID, *, owner_id: UUID) -> AiGenerationJob:
        job = self._repo.get_job(job_id, owner_id=owner_id)
        if job is None:
            raise NotFoundError("NOT_FOUND", "Generation job not found")
        return job

    @staticmethod
    def _validate_settings(question_count: int, question_kinds: list[AiQuestionKind]) -> None:
        if question_count < 1 or question_count > 100:
            raise ValidationError("VALIDATION_ERROR", "questionCount must be between 1 and 100")
        if not question_kinds:
            raise ValidationError("VALIDATION_ERROR", "At least one question type is required")
