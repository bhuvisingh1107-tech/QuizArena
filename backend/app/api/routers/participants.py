"""Participant-facing session routes (API_SPEC.md §12 companion paths).

Primary join entry remains ``/api/v1/join``. This router exposes the same
token-authenticated participant operations under ``/api/v1/participants`` for
clear Participant Service ownership in the modular monolith.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentParticipant, RequestId, get_db
from app.schemas.common import DataResponse, Meta
from app.schemas.participant import (
    JoinResponseData,
    JoinRoomMetaData,
    LeaveResponseData,
    ParticipantResponseData,
)
from app.services.participant_service import ParticipantService

router = APIRouter()


def get_participant_service(db: Annotated[Session, Depends(get_db)]) -> ParticipantService:
    return ParticipantService(db)


ParticipantServiceDep = Annotated[ParticipantService, Depends(get_participant_service)]


def _envelope(data, request_id: str, *, status_code: int = status.HTTP_200_OK) -> JSONResponse:
    payload = DataResponse(data=data, meta=Meta(request_id=request_id))
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


def _join_payload(participant, room, *, restored: bool) -> JoinResponseData:
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


@router.get(
    "/me",
    response_model=DataResponse[JoinResponseData],
    status_code=status.HTTP_200_OK,
    summary="Get current participant",
)
def get_participant(
    participant: CurrentParticipant,
    service: ParticipantServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    current = service.get_by_token(participant.session_token)
    assert current.live_room is not None
    return _envelope(_join_payload(current, current.live_room, restored=False), request_id)


@router.post(
    "/reconnect",
    response_model=DataResponse[JoinResponseData],
    status_code=status.HTTP_200_OK,
    summary="Reconnect participant session",
)
def reconnect_participant(
    participant: CurrentParticipant,
    service: ParticipantServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    restored, room = service.reconnect(participant.session_token)
    return _envelope(_join_payload(restored, room, restored=True), request_id)


@router.post(
    "/leave",
    response_model=DataResponse[LeaveResponseData],
    status_code=status.HTTP_200_OK,
    summary="Leave room",
)
def leave_participant(
    participant: CurrentParticipant,
    service: ParticipantServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    left = service.leave(participant.session_token)
    return _envelope(
        LeaveResponseData(id=left.id, left=True, state=left.state),
        request_id,
    )
