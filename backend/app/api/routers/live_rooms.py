"""Live room creation and control routes (API_SPEC.md §11)."""

from typing import Annotated
from uuid import UUID
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import AppSettings, CurrentAdmin, RequestId, get_db
from app.api.websocket.connection_manager import connection_manager
from app.api.websocket.events import ServerEventType
from app.config import _is_absolute_http_origin
from app.models.enums import LobbySubState, RoomState
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
from app.schemas.participant import AdminParticipantItem, AdminParticipantListData
from app.schemas.results import ResultsData
from app.services.live_room_service import LiveRoomService
from app.services.quiz_execution_service import QuizExecutionService
from app.services.results_service import ResultsService

router = APIRouter()


def _spa_origin_from_request(request: Request) -> str | None:
    """Prefer the browser Origin so join/display URLs match the SPA host."""
    origin = (request.headers.get("origin") or "").strip()
    if origin and _is_absolute_http_origin(origin):
        return origin.rstrip("/")

    referer = (request.headers.get("referer") or "").strip()
    if referer:
        parsed = urlparse(referer)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            candidate = f"{parsed.scheme}://{parsed.netloc}"
            if _is_absolute_http_origin(candidate):
                return candidate
    return None


def get_live_room_service(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: AppSettings,
) -> LiveRoomService:
    return LiveRoomService(db, settings, spa_origin=_spa_origin_from_request(request))


def get_results_service(db: Annotated[Session, Depends(get_db)]) -> ResultsService:
    return ResultsService(db)


def _lifecycle_payload(room: LiveRoom, db: Session) -> dict:
    payload: dict = {
        "roomId": str(room.id),
        "state": room.state.value,
        "lobbySubState": room.lobby_sub_state.value if room.lobby_sub_state else None,
        "codesExpired": room.codes_expired,
    }
    if room.state in {RoomState.PAUSED, RoomState.ACTIVE}:
        execution = QuizExecutionService(db).get_execution_state(room.id)
        if execution.question is not None:
            ends = QuizExecutionService._timer_ends_at_ts(room, execution.question)
            if ends is not None:
                from datetime import UTC, datetime

                ends_at = (
                    datetime.fromtimestamp(ends, tz=UTC).isoformat().replace("+00:00", "Z")
                )
                payload["timerEndsAt"] = ends_at
                payload["timerPaused"] = room.state == RoomState.PAUSED
    return payload


async def _broadcast_lifecycle(room: LiveRoom, event_type: str, db: Session) -> None:
    payload = _lifecycle_payload(room, db)
    await connection_manager.broadcast_to_room(room.id, event_type, payload)
    await connection_manager.broadcast_to_room(
        room.id,
        ServerEventType.ROOM_STATE_CHANGED,
        payload,
    )


LiveRoomServiceDep = Annotated[LiveRoomService, Depends(get_live_room_service)]
ResultsServiceDep = Annotated[ResultsService, Depends(get_results_service)]


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
    admin: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    room = service.create(body, owner_id=admin.id)
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
    admin: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    state: Annotated[RoomState | None, Query()] = None,
) -> JSONResponse:
    items, total = service.list(offset=offset, limit=limit, state=state, owner_id=admin.id)
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
    admin: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    room = service.get(room_id, owner_id=admin.id)
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
    admin: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    room = service.update_config(room_id, body, owner_id=admin.id)
    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/open-lobby",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Open lobby (Setup → Lobby)",
)
async def open_lobby(
    room_id: UUID,
    admin: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    room = service.open_lobby(room_id, owner_id=admin.id)
    await _broadcast_lifecycle(room, ServerEventType.ROOM_LOBBY_OPENED, db)
    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/toggle-lobby",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Toggle lobby open/closed",
)
async def toggle_lobby(
    room_id: UUID,
    admin: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    room = service.toggle_lobby(room_id, owner_id=admin.id)
    event = (
        ServerEventType.ROOM_LOBBY_OPENED
        if room.lobby_sub_state == LobbySubState.OPEN
        else ServerEventType.ROOM_LOBBY_CLOSED
    )
    await _broadcast_lifecycle(room, event, db)
    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/start",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Start session (Lobby → Active) and open the first question",
)
async def start_session(
    room_id: UUID,
    admin: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    # Persist Lobby → Active before any question broadcast so submit validation
    # and timers share the same committed room state.
    room = service.start(room_id, owner_id=admin.id)
    if room.state != RoomState.ACTIVE:
        from app.core.exceptions import ValidationError

        raise ValidationError(
            "ROOM_NOT_ACTIVE",
            f"Start Quiz failed to activate room (current: '{room.state.value}')",
        )

    await _broadcast_lifecycle(room, ServerEventType.ROOM_SESSION_STARTED, db)

    # Open first question immediately — host only needs Start Quiz.
    from app.core.exceptions import QuizArenaError
    from app.api.websocket.broadcast_helpers import (
        broadcast_execution_events,
        schedule_after_question_started,
    )

    try:
        result = QuizExecutionService(db).start_first_question(room_id)
        await broadcast_execution_events(room_id, result.events)
        schedule_after_question_started(room_id, result.events)
        room = result.room
    except QuizArenaError:
        # Room is Active; host can recover via admin:start_question if needed.
        pass

    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/pause",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Pause session (Active → Paused)",
)
async def pause_session(
    room_id: UUID,
    admin: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    room = service.pause(room_id, owner_id=admin.id)
    await _broadcast_lifecycle(room, ServerEventType.ROOM_PAUSED, db)
    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/resume",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Resume session (Paused → Active)",
)
async def resume_session(
    room_id: UUID,
    admin: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    room = service.resume(room_id, owner_id=admin.id)
    await _broadcast_lifecycle(room, ServerEventType.ROOM_RESUMED, db)
    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/end",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="End session (Active/Paused → Completed)",
)
async def end_session(
    room_id: UUID,
    admin: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    """End via execution service so clients get quiz:completed + podium + leaderboard."""
    from app.core.exceptions import QuizArenaError
    from app.api.websocket.broadcast_helpers import broadcast_execution_events
    from app.services.timer_service import auto_progression

    auto_progression.cancel_room(room_id)
    # Ownership check before mutating execution.
    service.get(room_id, owner_id=admin.id)
    try:
        result = QuizExecutionService(db).end_quiz(room_id)
        await broadcast_execution_events(room_id, result.events)
        room = result.room
    except QuizArenaError:
        # Fallback for rooms already mid-transition: still force Completed + notify.
        room = service.end(room_id, owner_id=admin.id)
        await _broadcast_lifecycle(room, ServerEventType.ROOM_COMPLETED, db)

    return _envelope(_room_response(room, service), request_id)


@router.post(
    "/{room_id}/close",
    response_model=DataResponse[LiveRoomResponseData],
    status_code=status.HTTP_200_OK,
    summary="Close room (Lobby/Completed → Closed)",
)
async def close_room(
    room_id: UUID,
    admin: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    room = service.close(room_id, owner_id=admin.id)
    await _broadcast_lifecycle(room, ServerEventType.ROOM_CLOSED, db)
    return _envelope(_room_response(room, service), request_id)


@router.delete(
    "/{room_id}",
    response_model=DataResponse[LiveRoomDeleteData],
    status_code=status.HTTP_200_OK,
    summary="Delete live room (Setup or Closed only)",
)
def delete_live_room(
    room_id: UUID,
    admin: CurrentAdmin,
    service: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    service.delete(room_id, owner_id=admin.id)
    return _envelope(LiveRoomDeleteData(id=room_id, deleted=True), request_id)


@router.get(
    "/{room_id}/participants",
    response_model=DataResponse[AdminParticipantListData],
    status_code=status.HTTP_200_OK,
    summary="List room participants (admin)",
)
def list_room_participants(
    room_id: UUID,
    admin: CurrentAdmin,
    service: ResultsServiceDep,
    rooms: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    rooms.get(room_id, owner_id=admin.id)
    participants, ranks, total = service.list_participants_admin(room_id)
    items = [
        AdminParticipantItem(
            id=p.id,
            display_name=p.display_name,
            email=p.email,
            state=p.state,
            connection_status=p.connection_status,
            total_score=int(p.total_score or 0),
            streak=int(p.streak or 0),
            rank=rank,
            total_correct=int(p.total_correct or 0),
            total_incorrect=int(p.total_incorrect or 0),
            unanswered_count=int(p.unanswered_count or 0),
            joined_at=p.joined_at,
        )
        for p, rank in zip(participants, ranks, strict=True)
    ]
    return _envelope(AdminParticipantListData(items=items, total=total), request_id)


@router.get(
    "/{room_id}/results",
    response_model=DataResponse[ResultsData],
    status_code=status.HTTP_200_OK,
    summary="Session results and analytics",
)
def get_room_results(
    room_id: UUID,
    admin: CurrentAdmin,
    service: ResultsServiceDep,
    rooms: LiveRoomServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    rooms.get(room_id, owner_id=admin.id)
    data = service.get_results(room_id)
    return _envelope(data, request_id)


@router.get(
    "/{room_id}/results/export",
    status_code=status.HTTP_200_OK,
    summary="Export session results as CSV",
)
def export_room_results(
    room_id: UUID,
    admin: CurrentAdmin,
    service: ResultsServiceDep,
    rooms: LiveRoomServiceDep,
) -> Response:
    rooms.get(room_id, owner_id=admin.id)
    csv_text = service.export_csv(room_id)
    filename = f"room-{room_id}-results.csv"
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
