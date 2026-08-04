"""Persist reviewed AI drafts into the existing quiz / section / question tables."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.enums import AiJobStatus, QuestionType, QuizStatus
from app.repositories.ai_generation_repository import AiGenerationRepository
from app.schemas.answer_option import AnswerOptionCreateRequest
from app.schemas.question import QuestionCreateRequest
from app.schemas.quiz import QuizCreateRequest
from app.schemas.section import SectionCreateRequest
from app.services.answer_option_service import AnswerOptionService
from app.services.question_service import QuestionService
from app.services.quiz_service import QuizService
from app.services.section_service import SectionService

logger = logging.getLogger(__name__)


class AiSaveService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._jobs = AiGenerationRepository(session)
        self._quizzes = QuizService(session)
        self._sections = SectionService(session)
        self._questions = QuestionService(session)
        self._options = AnswerOptionService(session)

    def save_job_as_quiz(self, job_id: UUID, *, owner_id: UUID) -> UUID:
        """Create (or return existing) Draft quiz from an AI job. Idempotent."""
        from app.services.ai.quality import assert_no_placeholders

        job = self._jobs.get_job(job_id, owner_id=owner_id)
        if job is None:
            raise NotFoundError("NOT_FOUND", "Generation job not found")
        if job.result_quiz_id is not None:
            logger.info("AI job %s already saved as quiz %s", job_id, job.result_quiz_id)
            return job.result_quiz_id

        # Ensure relationship collections are loaded from DB (not a stale empty cache).
        self._session.expire(job, ["sections"])
        job = self._jobs.get_job(job_id, owner_id=owner_id)
        if job is None:
            raise NotFoundError("NOT_FOUND", "Generation job not found")
        if not job.sections:
            raise ValidationError("VALIDATION_ERROR", "Job has no sections to save")

        # Final safety gate — never persist template/placeholder content.
        for section in job.sections:
            assert_no_placeholders(section.name, field="section.name")
            for question in section.questions:
                assert_no_placeholders(question.prompt_text, field="question.prompt")
                if question.explanation:
                    assert_no_placeholders(question.explanation, field="question.explanation")
                for raw in question.options_json or []:
                    if isinstance(raw, dict):
                        assert_no_placeholders(str(raw.get("text") or ""), field="question.option")

        title = (job.title or job.topic or "AI Generated Quiz").strip()[:255]
        quiz = self._quizzes.create(
            QuizCreateRequest(
                title=title,
                description=f"Generated via AI ({job.mode.value})"
                + (f" — {job.topic}" if job.topic else ""),
            ),
            owner_id=owner_id,
        )

        total_questions = 0
        for section_draft in sorted(job.sections, key=lambda s: s.sort_order):
            if not section_draft.questions:
                continue
            section = self._sections.create(
                quiz.id,
                SectionCreateRequest(name=section_draft.name[:255], sort_order=section_draft.sort_order),
                owner_id=owner_id,
            )
            for q_draft in sorted(section_draft.questions, key=lambda q: q.sort_order):
                options = q_draft.options_json or []
                if not isinstance(options, list):
                    raise ValidationError(
                        "MCQ_INVALID",
                        "MCQ must contain exactly 4 options.",
                        status_code=400,
                    )
                from app.models.enums import AiQuestionKind
                from app.services.ai.quality import validate_question_payload

                validate_question_payload(
                    {
                        "promptText": q_draft.prompt_text,
                        "explanation": q_draft.explanation or ("x" * 24),
                        "kind": q_draft.kind.value if hasattr(q_draft.kind, "value") else str(q_draft.kind),
                        "options": options,
                    },
                    index=q_draft.sort_order,
                )
                allow_multiple = q_draft.kind == AiQuestionKind.MULTIPLE_CORRECT
                question = self._questions.create(
                    quiz.id,
                    section.id,
                    QuestionCreateRequest(
                        question_type=QuestionType.TEXT,
                        prompt_text=q_draft.prompt_text,
                        explanation=q_draft.explanation,
                        base_points=1,
                        time_limit_seconds=q_draft.estimated_time_seconds or 20,
                        allow_multiple_correct=allow_multiple,
                        sort_order=q_draft.sort_order,
                    ),
                    owner_id=owner_id,
                )
                for opt_index, raw in enumerate(options):
                    if not isinstance(raw, dict):
                        continue
                    text = str(raw.get("text") or "").strip()
                    if not text:
                        continue
                    self._options.create(
                        quiz.id,
                        section.id,
                        question.id,
                        AnswerOptionCreateRequest(
                            text=text[:500],
                            is_correct=bool(raw.get("isCorrect")),
                            sort_order=opt_index,
                        ),
                        owner_id=owner_id,
                    )
                total_questions += 1

        if total_questions == 0:
            raise ValidationError("VALIDATION_ERROR", "No valid questions to save")

        quiz.status = QuizStatus.DRAFT
        job.result_quiz_id = quiz.id
        self._session.commit()
        logger.info(
            "AI job %s saved as quiz %s (%s questions)",
            job_id,
            quiz.id,
            total_questions,
        )
        return quiz.id
