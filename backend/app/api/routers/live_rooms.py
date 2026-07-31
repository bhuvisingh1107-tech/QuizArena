"""Live room creation and control routes (API_SPEC.md §11)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import AppSettings, CurrentAdmin, RequestId, get_db
from app.models.enums import RoomState
from app.models.live_room import LiveRoom
from app.schemas.common import DataResponse, Meta
from app.schemas.live_room import (
    LiveRoomCreateRequest,
    LiveRoomDeleteData,
    LiveRoomListData,
    LiveRoomResponseData,
    RoomConfigData,
    RoomConfigResponseData,
)
from app.services.live_room_service import LiveRoomService

router = APIRouter()


def get_live_room_service(
    db: Annotated[Session, Depends(get_db)],
    settings: AppSettings,
) -> LiveRoomService:
    return LiveRoomService(db, settings)


LiveRoomServiceDep = Annotated[LiveRoomService, Depends(get_live_room_service)]


def _room_response(room: LiveRoom, service: LiveRoomService) -> LiveRoomResponseData:
    config = (
        RoomConfigResponseData.model_validate(room.config) if room.config is not None else None
    )
    section_count = len(room.session_sections) if room.session_sections is not None else 0
    question_count = len(room.session_questions) if room.session_questions is not None else 0
    return LiveRoomResponseData(
        id=room.id,
        quiz_id=room.quiz_id,
        state=room.state,
        lobby_sub_state=room.lobby_sub_state,
        room_code=room.room_code,
        secret_token=room.secret_token,
        quiz_title_snapshot=room.quiz_title_snapshot,
        current_question_index=room.current_question_index,
        codes_expired=room.codes_expired,
        join_url=service.join_url(room.room_code),
        display_url=service.display_url(room.secret_token),
        qr_target=service.qr_target(room.room_code),
        config=config,
        section_count=section_count,
        question_count=question_count,
        started_at=room.started_at,
        completed_at=room.completed_at,
        closed_at=room.closed_at,
        created_at=room.created_at,
        updated_at=room.updated_at,
    )


def _envelope(data, request_id: str, *, status_code: int = status.HTTP_200_OK) -> JSONResponse:
    payload = DataResponse(data=data, meta=Meta(request_id=request_id))
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


@router.post(
    "",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_201_CREATED,
    summary="Create live room",
)
def create_live_room(
    body: LiveRoomCreateRequest,
    _: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    room = service.create(body)
    return _envelope(
        _room_response(room, service),
        request_id,
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "",
    response_model=DataResponse[LiveRoomListData],
    status_code=status.HTTP_200_OK,
    summary="List live rooms",
)
def list_live_rooms(
    _: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    state: Annotated[RoomState | None, Query()] = None,
) -> JSONResponse:
    items, total = service.list(offset=offset, limit=limit, state=state)
    data = LiveRoomListData(
        items=[_room_response(room, service) for room in items],
        total=total,
    )
    return _envelope(data, request_id)


@router.get(
    "/{room_id}",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Get live room",
)
def get_live_room(
    room_id: UUID,
    _: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    room = service.get(room_id)
    return _envelope(_room_response(room, service), request_id)


@router.patch(
    "/{room_id}/config",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Update room configuration (Setup only)",
)
def update_room_config(
    room_id: UUID,
    body: RoomConfigData,
    _: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    room = service.update_config(room_id, body)
    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/open-lobby",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Open lobby (Setup → Lobby)",
)
def open_lobby(
    room_id: UUID,
    _: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    room = service.open_lobby(room_id)
    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/toggle-lobby",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Toggle lobby open/closed",
)
def toggle_lobby(
    room_id: UUID,
    _: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    room = service.toggle_lobby(room_id)
    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/start",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Start session (Lobby → Active)",
)
def start_session(
    room_id: UUID,
    _: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    room = service.start(room_id)
    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/pause",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Pause session (Active → Paused)",
)
def pause_session(
    room_id: UUID,
    _: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    room = service.pause(room_id)
    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/resume",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Resume session (Paused → Active)",
)
def resume_session(
    room_id: UUID,
    _: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    room = service.resume(room_id)
    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/end",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="End session (Active/Paused → Completed)",
)
def end_session(
    room_id: UUID,
    _: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    room = service.end(room_id)
    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/close",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Close room (Lobby/Completed → Closed)",
)
def close_room(
    room_id: UUID,
    _: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    room = service.close(room_id)
    return _envelope(_room_response(room, service), request_id)


@router.delete(
    "/{room_id}",
    response_model=DataResponse[LiveRoomDeleteData],
    status_code=status.HTTP_200_OK,
    summary="Delete live room (Setup or Closed only)",
)
def delete_live_room(
    room_id: UUID,
    _: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    service.delete(room_id)
    return _envelope(LiveRoomDeleteData(id=room_id, deleted=True), request_id)
