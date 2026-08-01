"""Media upload, metadata, delete, serve, and attach routes (API_SPEC.md §10)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.deps import AppSettings, CurrentAdmin, RequestId, bearer_scheme, get_db
from app.core.exceptions import AuthenticationError, AuthorizationError, ValidationError
from app.models.enums import MediaCategory
from app.models.session_question import SessionQuestion
from app.schemas.common import DataResponse, Meta
from app.schemas.media import (
    MediaAttachData,
    MediaAttachRequest,
    MediaDeleteData,
    MediaListData,
    MediaResponseData,
)
from app.services.auth_service import AuthService
from app.services.media_service import MediaService
from app.services.participant_service import ParticipantService
from app.config import get_settings

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
    "",
    response_model=DataResponse[MediaListData],
    status_code=status.HTTP_200_OK,
    summary="List media for a quiz",
)
def list_media(
    _: CurrentAdmin,
    service: MediaServiceDep,
    request_id: RequestId,
    quiz_id: Annotated[UUID, Query(alias="quizId")],
    category: Annotated[MediaCategory | None, Query()] = None,
) -> JSONResponse:
    items = service.list_for_quiz(quiz_id, category=category)
    data = MediaListData(
        items=[
            _media_response(media, url=MediaService.public_url(media.id)) for media in items
        ],
        total=len(items),
    )
    return _envelope(data, request_id)


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
    service: MediaServiceDep,
    db: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    token: Annotated[
        str | None,
        Query(description="Participant session token or display secret token"),
    ] = None,
) -> Response:
    """Serve media to admins, participants, or the room display for attached media."""
    bearer = credentials.credentials if credentials and credentials.credentials else None
    raw_token = bearer or token
    if not raw_token:
        raise AuthenticationError("AUTH_ERROR", "Missing authentication token")

    allowed = False
    try:
        AuthService(db, get_settings()).get_admin_from_token(raw_token)
        allowed = True
    except AuthenticationError:
        allowed = False

    if not allowed:
        from app.models.live_room import LiveRoom

        room = db.query(LiveRoom).filter(LiveRoom.secret_token == raw_token).first()
        if room is not None:
            in_room = (
                db.query(SessionQuestion)
                .filter(
                    SessionQuestion.live_room_id == room.id,
                    SessionQuestion.media_file_id == media_id,
                )
                .first()
                is not None
            )
            if not in_room:
                raise AuthorizationError(
                    "FORBIDDEN",
                    "Media is not available for this display session",
                )
            allowed = True

    if not allowed:
        try:
            participant = ParticipantService(db).get_by_token(raw_token)
        except AuthenticationError as exc:
            raise AuthenticationError(
                "AUTH_ERROR",
                "Invalid authentication token",
            ) from exc
        in_room = (
            db.query(SessionQuestion)
            .filter(
                SessionQuestion.live_room_id == participant.live_room_id,
                SessionQuestion.media_file_id == media_id,
            )
            .first()
            is not None
        )
        if not in_room:
            raise AuthorizationError(
                "FORBIDDEN",
                "Media is not available for this participant session",
            )

    media, data = service.read_content(media_id)
    raw_name = str(media.original_filename or media.id)
    safe_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in raw_name)[:180]
    headers = {
        "Content-Disposition": f'inline; filename="{safe_name}"',
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
