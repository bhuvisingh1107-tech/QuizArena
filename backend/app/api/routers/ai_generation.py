"""AI quiz generation routes — upload, generate, review, save."""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import AppSettings, CurrentAdmin, RequestId, get_db
from app.core.exceptions import QuizArenaError, ValidationError
from app.models.ai_generation import AiGeneratedQuestion, AiGeneratedSection, AiGenerationJob
from app.schemas.ai_generation import (
    AiGenerateDocumentRequest,
    AiGenerateTopicRequest,
    AiGeneratedQuestionData,
    AiGeneratedSectionData,
    AiJobData,
    AiJobListData,
    AiQuestionPatchRequest,
    AiSaveRequest,
    AiSaveResultData,
    AiSourceFileData,
    AiSourceReferenceData,
)
from app.schemas.common import DataResponse, Meta
from app.services.ai.extractors import ALLOWED_EXTENSIONS, LEGACY_UNSUPPORTED
from app.services.ai.generation_service import AiGenerationService
from app.services.ai.job_worker import ai_job_worker
from app.services.ai.save_service import AiSaveService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_ai_service(
    db: Annotated[Session, Depends(get_db)],
    settings: AppSettings,
) -> AiGenerationService:
    return AiGenerationService(db, settings)


AiServiceDep = Annotated[AiGenerationService, Depends(get_ai_service)]


def _envelope(data: Any, request_id: str, *, status_code: int = status.HTTP_200_OK) -> JSONResponse:
    payload = DataResponse(data=data, meta=Meta(request_id=request_id))
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


def _schedule(background_tasks: BackgroundTasks, job_id: UUID, *, request_id: str, context: str) -> None:
    try:
        logger.info(
            "AI schedule requested",
            extra={"request_id": request_id, "job_id": str(job_id), "context": context},
        )
        ai_job_worker.schedule(background_tasks, job_id)
    except Exception as exc:
        logger.exception(
            "AI worker schedule failed",
            extra={"request_id": request_id, "job_id": str(job_id), "context": context},
        )
        raise QuizArenaError(
            "AI_WORKER_UNAVAILABLE",
            "Generation job was created but could not be scheduled. Please retry in a moment.",
            details=[{"jobId": str(job_id), "context": context}],
            status_code=503,
        ) from exc


def _map_question(question: AiGeneratedQuestion) -> AiGeneratedQuestionData:
    options = question.options_json if isinstance(question.options_json, list) else []
    return AiGeneratedQuestionData(
        id=question.id,
        kind=question.kind,
        prompt_text=question.prompt_text,
        explanation=question.explanation,
        difficulty=question.difficulty,
        topic_label=question.topic_label,
        estimated_time_seconds=question.estimated_time_seconds,
        options=options,
        source_locator=question.source_locator,
        sort_order=question.sort_order,
    )


def _map_section(section: AiGeneratedSection) -> AiGeneratedSectionData:
    questions = sorted(section.questions, key=lambda q: q.sort_order)
    return AiGeneratedSectionData(
        id=section.id,
        name=section.name,
        summary=section.summary,
        sort_order=section.sort_order,
        concepts=list(section.concepts_json or []),
        questions=[_map_question(q) for q in questions],
    )


def _map_job(job: AiGenerationJob) -> AiJobData:
    return AiJobData(
        id=job.id,
        mode=job.mode,
        status=job.status,
        progress_percent=job.progress_percent,
        progress_message=job.progress_message,
        error_code=job.error_code,
        error_message=job.error_message,
        topic=job.topic,
        title=job.title,
        language=job.language,
        question_count=job.question_count,
        difficulty=job.difficulty,
        question_kinds=[str(k) for k in (job.question_kinds or [])],
        result_quiz_id=job.result_quiz_id,
        source_files=[
            AiSourceFileData(
                id=f.id,
                original_filename=f.original_filename,
                mime_type=f.mime_type,
                file_size=f.file_size,
                extractor=f.extractor,
            )
            for f in job.source_files
        ],
        sources=[
            AiSourceReferenceData(
                id=s.id,
                kind=s.kind,
                title=s.title,
                locator=s.locator,
                publisher=s.publisher,
            )
            for s in job.sources
        ],
        sections=[_map_section(s) for s in sorted(job.sections, key=lambda x: x.sort_order)],
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.post(
    "/generate/document",
    response_model=DataResponse[AiJobData],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a document-mode AI generation job (awaiting upload)",
)
async def create_document_job(
    payload: AiGenerateDocumentRequest,
    admin: CurrentAdmin,
    service: AiServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    job = service.create_document_job(
        owner_id=admin.id,
        title=payload.title,
        language=payload.language,
        question_count=payload.question_count,
        difficulty=payload.difficulty,
        question_kinds=payload.question_kinds,
    )
    return _envelope(_map_job(job), request_id, status_code=status.HTTP_202_ACCEPTED)


@router.post(
    "/generate/topic",
    response_model=DataResponse[AiJobData],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a topic-mode AI generation job and start processing",
)
async def create_topic_job(
    payload: AiGenerateTopicRequest,
    admin: CurrentAdmin,
    service: AiServiceDep,
    request_id: RequestId,
    settings: AppSettings,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    logger.info(
        "AI generate/topic request received topic=%s provider=%s",
        payload.topic,
        settings.ai_provider,
        extra={"request_id": request_id, "owner_id": str(admin.id)},
    )
    job = service.create_topic_job(
        owner_id=admin.id,
        topic=payload.topic,
        title=payload.title,
        language=payload.language,
        question_count=payload.question_count,
        difficulty=payload.difficulty,
        question_kinds=payload.question_kinds,
    )
    _schedule(background_tasks, job.id, request_id=request_id, context="generate/topic")
    refreshed = service.get_job(job.id, owner_id=admin.id)
    return _envelope(_map_job(refreshed), request_id, status_code=status.HTTP_202_ACCEPTED)


@router.post(
    "/upload",
    response_model=DataResponse[AiJobData],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload study material for a document job and start processing",
)
async def upload_source(
    admin: CurrentAdmin,
    service: AiServiceDep,
    request_id: RequestId,
    background_tasks: BackgroundTasks,
    job_id: Annotated[UUID, Form(alias="jobId")],
    file: UploadFile = File(...),
) -> JSONResponse:
    filename = file.filename or "upload.bin"
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix in LEGACY_UNSUPPORTED:
        raise ValidationError("UNSUPPORTED_FILE_TYPE", LEGACY_UNSUPPORTED[suffix])
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            "UNSUPPORTED_FILE_TYPE",
            f"Unsupported file type '{suffix}'. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    data = await file.read()
    service.attach_upload(
        job_id,
        owner_id=admin.id,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    _schedule(background_tasks, job_id, request_id=request_id, context="upload")
    job = service.get_job(job_id, owner_id=admin.id)
    return _envelope(_map_job(job), request_id, status_code=status.HTTP_202_ACCEPTED)


@router.get(
    "/jobs",
    response_model=DataResponse[AiJobListData],
    summary="List recent AI generation jobs for the current host",
)
def list_jobs(
    admin: CurrentAdmin,
    service: AiServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    items = service.list_jobs(owner_id=admin.id)
    return _envelope(AiJobListData(items=[_map_job(j) for j in items]), request_id)


@router.get(
    "/jobs/{job_id}",
    response_model=DataResponse[AiJobData],
    summary="Get AI generation job status and draft content",
)
def get_job(
    job_id: UUID,
    admin: CurrentAdmin,
    service: AiServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    job = service.get_job(job_id, owner_id=admin.id)
    return _envelope(_map_job(job), request_id)


@router.get(
    "/generated/{job_id}",
    response_model=DataResponse[AiJobData],
    summary="Alias for job detail (review payload)",
)
def get_generated(
    job_id: UUID,
    admin: CurrentAdmin,
    service: AiServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    return get_job(job_id, admin, service, request_id)


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=DataResponse[AiJobData],
    summary="Cancel a running or queued generation job",
)
def cancel_job(
    job_id: UUID,
    admin: CurrentAdmin,
    service: AiServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    ai_job_worker.cancel(job_id)
    job = service.cancel_job(job_id, owner_id=admin.id)
    return _envelope(_map_job(job), request_id)


@router.patch(
    "/question/{question_id}",
    response_model=DataResponse[AiGeneratedQuestionData],
    summary="Edit a generated draft question",
)
def patch_question(
    question_id: UUID,
    payload: AiQuestionPatchRequest,
    admin: CurrentAdmin,
    service: AiServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    patch: dict[str, Any] = payload.model_dump(by_alias=True, exclude_unset=True)
    if "options" in patch and patch["options"] is not None:
        patch["options"] = [
            o if isinstance(o, dict) else o.model_dump(by_alias=True)
            for o in (payload.options or [])
        ]
    question = service.update_question(question_id, owner_id=admin.id, patch=patch)
    return _envelope(_map_question(question), request_id)


@router.delete(
    "/question/{question_id}",
    response_model=DataResponse[dict[str, object]],
    summary="Delete a generated draft question",
)
def delete_question(
    question_id: UUID,
    admin: CurrentAdmin,
    service: AiServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    service.delete_question(question_id, owner_id=admin.id)
    return _envelope({"id": str(question_id), "deleted": True}, request_id)


@router.post(
    "/regenerate/question/{question_id}",
    response_model=DataResponse[AiGeneratedQuestionData],
    summary="Regenerate a single draft question",
)
def regenerate_question(
    question_id: UUID,
    admin: CurrentAdmin,
    service: AiServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    question = service.regenerate_question(question_id, owner_id=admin.id)
    return _envelope(_map_question(question), request_id)


@router.post(
    "/regenerate/section/{section_id}",
    response_model=DataResponse[AiGeneratedSectionData],
    summary="Regenerate all questions in a draft section",
)
def regenerate_section(
    section_id: UUID,
    admin: CurrentAdmin,
    service: AiServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    section = service.regenerate_section(section_id, owner_id=admin.id)
    return _envelope(_map_section(section), request_id)


@router.post(
    "/regenerate/quiz/{job_id}",
    response_model=DataResponse[AiJobData],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Regenerate the entire quiz draft for a job",
)
async def regenerate_quiz(
    job_id: UUID,
    admin: CurrentAdmin,
    service: AiServiceDep,
    request_id: RequestId,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    job = service.queue_full_regeneration(job_id, owner_id=admin.id)
    _schedule(background_tasks, job_id, request_id=request_id, context="regenerate/quiz")
    job = service.get_job(job_id, owner_id=admin.id)
    return _envelope(_map_job(job), request_id, status_code=status.HTTP_202_ACCEPTED)


@router.post(
    "/save",
    response_model=DataResponse[AiSaveResultData],
    summary="Save reviewed AI draft into a Draft quiz (idempotent)",
)
def save_job(
    payload: AiSaveRequest,
    admin: CurrentAdmin,
    request_id: RequestId,
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    quiz_id = AiSaveService(db).save_job_as_quiz(payload.job_id, owner_id=admin.id)
    return _envelope(AiSaveResultData(quiz_id=quiz_id, job_id=payload.job_id), request_id)
