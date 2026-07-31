"""Participant join validation routes (API_SPEC.md §12)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import RequestId, get_db
from app.core.rate_limit import join_rate_limiter
from app.models.live_room import LiveRoom
from app.models.participant import Participant
from app.schemas.common import DataResponse, Meta
from app.schemas.participant import (
    JoinRequest,
    JoinResponseData,
    JoinRoomMetaData,
    ParticipantResponseData,
)
from app.services.participant_service import ParticipantService

router = APIRouter()


def get_participant_service(db: Annotated[Session, Depends(get_db)]) -> ParticipantService:
    return ParticipantService(db)


ParticipantServiceDep = Annotated[ParticipantService, Depends(get_participant_service)]


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _join_payload(
    participant: Participant,
    room: LiveRoom,
    *,
    restored: bool,
) -> JoinResponseData:
    return JoinResponseData(
        session_token=participant.session_token,
        participant=ParticipantResponseData.model_validate(participant),
        room=JoinRoomMetaData(
            id=room.id,
            room_code=room.room_code,
            state=room.state,
            lobby_sub_state=room.lobby_sub_state,
            quiz_title=room.quiz_title_snapshot,
            codes_expired=room.codes_expired,
        ),
        restored=restored,
    )


def _envelope(data, request_id: str, *, status_code: int = status.HTTP_200_OK) -> JSONResponse:
    payload = DataResponse(data=data, meta=Meta(request_id=request_id))
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


@router.post(
    "",
    response_model=DataResponse[JoinResponseData],
    status_code=status.HTTP_200_OK,
    summary="Join live room (or restore by email)",
)
def join_room(
    body: JoinRequest,
    request: Request,
    service: ParticipantServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    """Public, rate-limited join — API_SPEC.md §12."""
    join_rate_limiter.check(_client_key(request))
    participant, room, restored = service.join(body)
    return _envelope(
        _join_payload(participant, room, restored=restored),
        request_id,
        status_code=status.HTTP_201_CREATED if not restored else status.HTTP_200_OK,
    )
