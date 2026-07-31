"""Media upload, metadata, delete, serve, and attach routes (API_SPEC.md §10)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import AppSettings, CurrentAdmin, RequestId, get_db
from app.core.exceptions import ValidationError
from app.models.enums import MediaCategory
from app.schemas.common import DataResponse, Meta
from app.schemas.media import (
    MediaAttachData,
    MediaAttachRequest,
    MediaDeleteData,
    MediaResponseData,
)
from app.services.media_service import MediaService

router = APIRouter()

_MAX_READ_BYTES = 15 * 1024 * 1024  # largest allowed category (question audio)


def get_media_service(
    db: Annotated[Session, Depends(get_db)],
    settings: AppSettings,
) -> MediaService:
    return MediaService(db, settings)


MediaServiceDep = Annotated[MediaService, Depends(get_media_service)]


def _media_response(media, *, url: str) -> MediaResponseData:
    return MediaResponseData(
        id=media.id,
        category=media.category,
        mime_type=media.mime_type,
        file_size=media.file_size,
        original_filename=media.original_filename,
        quiz_id=media.quiz_id,
        url=url,
        created_at=media.created_at,
        updated_at=media.updated_at,
    )


def _envelope(data, request_id: str, *, status_code: int = status.HTTP_200_OK) -> JSONResponse:
    payload = DataResponse(data=data, meta=Meta(request_id=request_id))
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


@router.post(
    "",
    response_model=DataResponse[MediaResponseData],
    status_code=status.HTTP_201_CREATED,
    summary="Upload media file",
)
async def upload_media(
    _: CurrentAdmin,
    service: MediaServiceDep,
    request_id: RequestId,
    file: Annotated[UploadFile, File()],
    category: Annotated[MediaCategory, Form()],
    quiz_id: Annotated[UUID | None, Form(alias="quizId")] = None,
) -> JSONResponse:
    data = await file.read(_MAX_READ_BYTES + 1)
    if not data:
        raise ValidationError("MISSING_FILE", "No file was uploaded")
    if len(data) > _MAX_READ_BYTES:
        raise ValidationError(
            "FILE_TOO_LARGE",
            f"File exceeds the maximum supported upload size of {_MAX_READ_BYTES} bytes",
        )

    media = service.upload(
        data=data,
        category=category,
        original_filename=file.filename,
        quiz_id=quiz_id,
        declared_content_type=file.content_type,
    )
    return _envelope(
        _media_response(media, url=MediaService.public_url(media.id)),
        request_id,
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "/{media_id}",
    response_model=DataResponse[MediaResponseData],
    status_code=status.HTTP_200_OK,
    summary="Get media metadata",
)
def get_media(
    media_id: UUID,
    _: CurrentAdmin,
    service: MediaServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    media = service.get(media_id)
    return _envelope(
        _media_response(media, url=MediaService.public_url(media.id)),
        request_id,
    )


@router.get(
    "/{media_id}/content",
    summary="Serve media file bytes",
    response_class=Response,
)
def serve_media(
    media_id: UUID,
    _: CurrentAdmin,
    service: MediaServiceDep,
) -> Response:
    media, data = service.read_content(media_id)
    headers = {
        "Content-Disposition": (
            f'inline; filename="{media.original_filename or media.id}"'
        ),
        "Cache-Control": "private, max-age=3600",
    }
    return Response(content=data, media_type=media.mime_type, headers=headers)


@router.delete(
    "/{media_id}",
    response_model=DataResponse[MediaDeleteData],
    status_code=status.HTTP_200_OK,
    summary="Delete media file",
)
def delete_media(
    media_id: UUID,
    _: CurrentAdmin,
    service: MediaServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    service.delete(media_id)
    return _envelope(MediaDeleteData(id=media_id, deleted=True), request_id)


@router.post(
    "/{media_id}/attach",
    response_model=DataResponse[MediaAttachData],
    status_code=status.HTTP_200_OK,
    summary="Attach media to a question",
)
def attach_media(
    media_id: UUID,
    body: MediaAttachRequest,
    _: CurrentAdmin,
    service: MediaServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    media, question_id = service.attach_to_question(media_id, body)
    return _envelope(
        MediaAttachData(
            media_id=media.id,
            question_id=question_id,
            media_file_id=media.id,
        ),
        request_id,
    )
