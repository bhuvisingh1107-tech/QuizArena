"""Orchestrates document/topic → structured sections → draft questions."""

from __future__ import annotations

import logging
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
from app.services.ai.quality import validate_question_payload, validate_questions_batch
from app.services.ai.topic_focus import (
    is_broad_topic,
    suggested_subtopic_example,
    topic_narrowing_instruction,
)
from app.services.ai.trusted_sources import trusted_source_seeds
from app.storage.local import LocalStorageBackend

logger = logging.getLogger(__name__)

# Temporary debug logging for AI generation pipeline (broad-topic diagnosis).
_AI_DEBUG = True
_MAX_QUESTION_ATTEMPTS = 3


class AiGenerationService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._repo = AiGenerationRepository(session)
        self._storage_root = Path(self._settings.storage_path).resolve()
        self._storage_root.mkdir(parents=True, exist_ok=True)
        (self._storage_root / "ai-sources").mkdir(parents=True, exist_ok=True)
        self._provider = get_ai_provider(self._settings)
        logger.info(
            "AiGenerationService ready provider=%s embedding_model=%s chat_model=%s",
            self._provider.name,
            self._settings.ai_embedding_model,
            self._settings.ai_chat_model,
        )

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

        logger.info(
            "AI job %s run start mode=%s provider=%s topic=%s",
            job_id,
            job.mode.value,
            self._provider.name,
            job.topic,
        )
        job.started_at = datetime.now(UTC)
        try:
            if job.mode == AiGenerationMode.DOCUMENT:
                self._run_document(job)
            else:
                self._run_topic(job)
            job.status = AiJobStatus.COMPLETED
            job.progress_percent = 95
            job.progress_message = "Saving quiz"
            self._repo.commit()

            # Auto-create Draft quiz so it appears in My Quizzes immediately.
            try:
                from app.services.ai.save_service import AiSaveService

                self._session.expire(job, ["sections", "sources", "source_files"])
                quiz_id = AiSaveService(self._session).save_job_as_quiz(
                    job.id,
                    owner_id=job.owner_id,
                )
                job = self._repo.get_job(job_id) or job
                job.result_quiz_id = quiz_id
                job.progress_percent = 100
                job.progress_message = "Ready — quiz saved to My Quizzes"
                job.completed_at = datetime.now(UTC)
                self._repo.commit()
                logger.info("AI job %s auto-saved quiz %s", job_id, quiz_id)
            except Exception:
                logger.exception("AI job %s auto-save failed; draft remains reviewable", job_id)
                job = self._repo.get_job(job_id) or job
                job.status = AiJobStatus.COMPLETED
                job.progress_percent = 100
                job.progress_message = "Ready for review (auto-save skipped)"
                job.completed_at = datetime.now(UTC)
                self._repo.commit()

            logger.info("AI job %s completed sections=%s", job_id, len(job.sections))
        except Exception as exc:
            self._session.rollback()
            job = self._repo.get_job(job_id) or job
            job.status = AiJobStatus.FAILED
            job.error_code = getattr(exc, "code", None) or "AI_GENERATION_FAILED"
            # Prefer domain message; append provider details (e.g. full Gemini HTTP body)
            # so the admin UI shows the exact upstream error, not a truncated generic line.
            message = str(getattr(exc, "message", None) or exc)
            details = getattr(exc, "details", None) or []
            if details:
                import json

                message = (
                    f"{message}\n\nProvider details:\n"
                    f"{json.dumps(details, default=str, indent=2)}"
                )
            job.error_message = message[:50000]
            job.progress_message = "Failed"
            job.completed_at = datetime.now(UTC)
            self._repo.commit()
            logger.exception("AI job %s failed: %s", job_id, job.error_message)
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
        logger.info(
            "AI job %s extracted text chars=%s sources=%s",
            job.id,
            len(full_text),
            len(job.source_files),
        )
        if len(full_text.strip()) < 40:
            raise ValidationError(
                "EMPTY_EXTRACTION",
                "Extracted text is too short to generate a meaningful quiz. "
                "Try a clearer document or a different file.",
            )
        self._set_progress(job, 25, AiJobStatus.EXTRACTING, "Chunking content")
        self._store_chunks(job, full_text)

        self._set_progress(job, 40, AiJobStatus.ANALYZING, "Detecting sections")
        outline = self._detect_structure(job, full_text)
        self._set_progress(job, 55, AiJobStatus.GENERATING, "Generating questions")
        self._generate_questions_for_outline(job, outline, full_text)

    def _run_topic(self, job: AiGenerationJob) -> None:
        assert job.topic
        broad = is_broad_topic(job.topic)
        logger.info(
            "AI job %s topic pipeline topic=%r broad=%s suggested_focus=%s",
            job.id,
            job.topic,
            broad,
            suggested_subtopic_example(job.topic) if broad else "(n/a)",
        )
        self._set_progress(job, 15, AiJobStatus.ANALYZING, "Planning sections from topic")
        outline = self._topic_outline(job)

        focus = str(outline.get("focusedSubtopic") or outline.get("title") or job.topic).strip()
        seed_topic = focus or job.topic
        if _AI_DEBUG:
            logger.info(
                "AI DEBUG job %s focused_subtopic=%r outline_title=%r section_count=%s",
                job.id,
                focus,
                outline.get("title"),
                len(outline.get("sections") or []),
            )
            for idx, section in enumerate(outline.get("sections") or []):
                if not isinstance(section, dict):
                    continue
                summary = str(section.get("summary") or "")
                logger.info(
                    "AI DEBUG job %s outline_section[%s] name=%r summary_chars=%s concepts=%s",
                    job.id,
                    idx,
                    section.get("name"),
                    len(summary),
                    section.get("concepts"),
                )

        for src in trusted_source_seeds(seed_topic) if self._settings.ai_enable_topic_web else []:
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
            if _AI_DEBUG:
                logger.info(
                    "AI DEBUG job %s trusted_source_seed title=%r url=%s",
                    job.id,
                    src.get("title"),
                    src.get("url"),
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
            if _AI_DEBUG:
                logger.info(
                    "AI DEBUG job %s outline_trusted_source title=%r url=%s",
                    job.id,
                    item.get("title"),
                    url,
                )

        # Topic mode uses outline summaries as synthetic source text.
        # Note: embeddings are stored for future RAG; generation today passes this
        # synthetic excerpt wholesale (URLs are attribution-only, not fetched).
        synthetic = self._build_topic_source_text(outline, job.topic)
        if _AI_DEBUG:
            logger.info(
                "AI DEBUG job %s synthetic_source_chars=%s preview=%r",
                job.id,
                len(synthetic),
                synthetic[:500],
            )
        self._store_chunks(job, synthetic or job.topic)
        self._set_progress(job, 55, AiJobStatus.GENERATING, "Generating questions")
        self._generate_questions_for_outline(job, outline, synthetic or job.topic)

    def _build_topic_source_text(self, outline: dict[str, Any], topic: str) -> str:
        """Build a dense synthetic source excerpt from the topic outline."""
        parts: list[str] = []
        focused = str(outline.get("focusedSubtopic") or outline.get("title") or topic).strip()
        parts.append(f"# Quiz focus: {focused}")
        parts.append(
            "The following teaching notes are the authoritative source for all questions. "
            "Use only these facts; do not invent unrelated material."
        )
        for raw in outline.get("sections") or []:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "").strip() or "Section"
            summary = str(raw.get("summary") or "").strip()
            concepts = [str(c).strip() for c in (raw.get("concepts") or []) if str(c).strip()]
            block = f"## {name}\n{summary}" if summary else f"## {name}"
            if concepts:
                block += f"\nKey concepts: {', '.join(concepts)}."
            if summary:
                # Reinforce teachable content so thin outlines still cue the LLM.
                block += (
                    f"\nExam focus: Write questions that test understanding of {name}"
                    f" within {focused}, using the definitions and relationships above."
                )
            parts.append(block)
        return "\n\n".join(parts).strip()

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
        logger.info(
            "AI job %s structure prompt ready source_chars=%s prompt_chars=%s",
            job.id,
            len(source_text),
            len(user),
        )
        data = self._chat_json_with_retry(
            [ChatMessage("system", system), ChatMessage("user", user)],
            temperature=0.2,
            expect_key="sections",
        )
        logger.info(
            "AI job %s structure parsed sections=%s",
            job.id,
            len(data.get("sections") or []),
        )
        return data

    def _topic_outline(self, job: AiGenerationJob) -> dict[str, Any]:
        system = load_prompt(TOPIC_OUTLINE_SYSTEM)
        guidance = topic_narrowing_instruction(job.topic or "")
        user = render_template(
            load_prompt(TOPIC_OUTLINE_USER),
            topic=job.topic or "",
            language=job.language,
            topic_focus_guidance=guidance,
        )
        logger.info(
            "AI job %s topic outline prompt ready provider=%s user_chars=%s topic=%s broad=%s",
            job.id,
            self._provider.name,
            len(user),
            job.topic,
            is_broad_topic(job.topic or ""),
        )
        if _AI_DEBUG:
            logger.info("AI DEBUG job %s FINAL topic_outline SYSTEM prompt:\n%s", job.id, system)
            logger.info("AI DEBUG job %s FINAL topic_outline USER prompt:\n%s", job.id, user)
        data = self._chat_json_with_retry(
            [ChatMessage("system", system), ChatMessage("user", user)],
            temperature=0.3,
            expect_key="sections",
        )
        if _AI_DEBUG:
            logger.info("AI DEBUG job %s topic_outline PARSED JSON: %s", job.id, data)
        logger.info(
            "AI job %s topic outline response sections=%s focused=%r",
            job.id,
            len(data.get("sections") or []),
            data.get("focusedSubtopic") or data.get("title"),
        )
        return data

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
            from app.services.ai.quality import validate_section_name

            validate_section_name(name, allow_generic=job.mode.value != "document")
            section = AiGeneratedSection(
                id=uuid4(),
                job_id=job.id,
                name=name,
                summary=str(raw.get("summary") or "")[:4000] or None,
                sort_order=sort_order,
                concepts_json=list(raw.get("concepts") or []),
            )
            job.sections.append(section)
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
        logger.info(
            "AI job %s question prompt section=%s source_chars=%s prompt_chars=%s count=%s",
            job.id,
            section_name,
            len(source_text),
            len(user),
            question_count,
        )
        if _AI_DEBUG:
            logger.info(
                "AI DEBUG job %s FINAL questions SYSTEM prompt (section=%s):\n%s",
                job.id,
                section_name,
                system,
            )
            logger.info(
                "AI DEBUG job %s FINAL questions USER prompt (section=%s):\n%s",
                job.id,
                section_name,
                user,
            )
        if len(source_text.strip()) < 20:
            raise ValidationError(
                "AI_SOURCE_TOO_SHORT",
                f"Not enough source text to generate questions for section '{section_name}'.",
            )

        last_error: Exception | None = None
        messages = [ChatMessage("system", system), ChatMessage("user", user)]
        for attempt in range(1, _MAX_QUESTION_ATTEMPTS + 1):
            try:
                data = self._provider.chat_json(
                    messages,
                    temperature=0.35 if attempt == 1 else 0.15,
                )
                if _AI_DEBUG:
                    logger.info(
                        "AI DEBUG job %s section=%s attempt=%s RAW parsed JSON keys=%s payload=%s",
                        job.id,
                        section_name,
                        attempt,
                        list(data.keys()),
                        data,
                    )
                raw_questions = [q for q in (data.get("questions") or []) if isinstance(q, dict)]
                if raw_questions and _AI_DEBUG:
                    logger.info(
                        "AI DEBUG job %s section=%s question[0].explanation before validation: %r",
                        job.id,
                        section_name,
                        raw_questions[0].get("explanation"),
                    )
                logger.info(
                    "AI job %s section=%s attempt=%s parsed_questions=%s keys=%s",
                    job.id,
                    section_name,
                    attempt,
                    len(raw_questions),
                    list(data.keys()),
                )
                validated = validate_questions_batch(raw_questions)
                logger.info(
                    "AI job %s section=%s validation ok questions=%s",
                    job.id,
                    section_name,
                    len(validated),
                )
                return validated[:question_count] if question_count else validated
            except Exception as exc:
                last_error = exc
                code = getattr(exc, "code", None)
                logger.warning(
                    "AI job %s section=%s question generation attempt %s failed code=%s: %s",
                    job.id,
                    section_name,
                    attempt,
                    code,
                    exc,
                )
                # Automatically regenerate when the model returned placeholder/stub text.
                if (
                    attempt < _MAX_QUESTION_ATTEMPTS
                    and isinstance(exc, ValidationError)
                    and code in {"AI_PLACEHOLDER_CONTENT", "AI_QUESTION_INVALID"}
                ):
                    repair = (
                        "Your previous JSON was rejected by the quality gate.\n"
                        f"Rejection: {getattr(exc, 'message', None) or exc}\n"
                        "Regenerate the FULL questions JSON now.\n"
                        "Requirements: every question must include promptText, options, "
                        "a correctly marked answer, and a real multi-sentence explanation "
                        "grounded in the source. Never use TODO, TBD, placeholder, "
                        "'Explanation goes here', '<explanation>', '{{...}}', "
                        "'Correct answer', 'Correct fact', or 'This checks understanding'."
                    )
                    messages = [
                        ChatMessage("system", system),
                        ChatMessage("user", user),
                        ChatMessage("user", repair),
                    ]
                    if _AI_DEBUG:
                        logger.info(
                            "AI DEBUG job %s section=%s scheduling placeholder repair attempt %s",
                            job.id,
                            section_name,
                            attempt + 1,
                        )
                    continue

        raise ValidationError(
            getattr(last_error, "code", None) or "AI_GENERATION_FAILED",
            str(getattr(last_error, "message", None) or last_error or "Question generation failed"),
        )

    def _chat_json_with_retry(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float,
        expect_key: str | None = None,
        attempts: int = 2,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                data = self._provider.chat_json(messages, temperature=temperature)
                if expect_key and not data.get(expect_key):
                    raise ValidationError(
                        "AI_PARSE_ERROR",
                        f"AI response missing '{expect_key}'.",
                    )
                return data
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "AI chat_json attempt %s/%s failed: %s",
                    attempt,
                    attempts,
                    exc,
                )
        raise ValidationError(
            getattr(last_error, "code", None) or "AI_PARSE_ERROR",
            str(
                getattr(last_error, "message", None)
                or last_error
                or "AI response could not be parsed"
            ),
        )

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
        if _AI_DEBUG:
            logger.info(
                "AI DEBUG job %s regenerate_question FINAL SYSTEM:\n%s",
                job.id,
                system,
            )
            logger.info(
                "AI DEBUG job %s regenerate_question FINAL USER:\n%s",
                job.id,
                user,
            )
        last_error: Exception | None = None
        messages = [ChatMessage("system", system), ChatMessage("user", user)]
        payload: dict[str, Any] | None = None
        for attempt in range(1, _MAX_QUESTION_ATTEMPTS + 1):
            try:
                data = self._provider.chat_json(messages, temperature=0.5 if attempt == 1 else 0.2)
                if _AI_DEBUG:
                    logger.info(
                        "AI DEBUG job %s regenerate_question attempt=%s RAW=%s",
                        job.id,
                        attempt,
                        data,
                    )
                # Provider may return {question: {...}} or the object itself.
                candidate = data.get("question") if isinstance(data.get("question"), dict) else data
                if not isinstance(candidate, dict):
                    raise ValidationError(
                        "AI_PARSE_ERROR", "Regenerated question payload was invalid"
                    )
                if _AI_DEBUG:
                    logger.info(
                        "AI DEBUG job %s regenerate_question explanation before validation: %r",
                        job.id,
                        candidate.get("explanation"),
                    )
                validate_question_payload(candidate, index=0)
                payload = candidate
                break
            except Exception as exc:
                last_error = exc
                code = getattr(exc, "code", None)
                logger.warning(
                    "AI job %s regenerate_question attempt %s failed code=%s: %s",
                    job.id,
                    attempt,
                    code,
                    exc,
                )
                if (
                    attempt < _MAX_QUESTION_ATTEMPTS
                    and isinstance(exc, ValidationError)
                    and code in {"AI_PLACEHOLDER_CONTENT", "AI_QUESTION_INVALID", "AI_PARSE_ERROR"}
                ):
                    messages = [
                        ChatMessage("system", system),
                        ChatMessage("user", user),
                        ChatMessage(
                            "user",
                            "Previous regenerate output was rejected: "
                            f"{getattr(exc, 'message', None) or exc}. "
                            "Return one complete question JSON with a real multi-sentence "
                            "explanation and no placeholder/stub text.",
                        ),
                    ]
                    continue
                if attempt >= _MAX_QUESTION_ATTEMPTS:
                    break

        if payload is None:
            raise ValidationError(
                getattr(last_error, "code", None) or "AI_GENERATION_FAILED",
                str(
                    getattr(last_error, "message", None)
                    or last_error
                    or "Question regeneration failed"
                ),
            )
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
        validate_question_payload(payload, index=sort_order)
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
        prompt = str(payload.get("promptText") or payload.get("prompt_text") or "").strip()
        explanation = str(payload.get("explanation") or "").strip() or None
        return AiGeneratedQuestion(
            id=uuid4(),
            job_id=job.id,
            section_id=section.id,
            kind=kind,
            prompt_text=prompt,
            explanation=explanation,
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
                or f"Section: {section.name}"
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
