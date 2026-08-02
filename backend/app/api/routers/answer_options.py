"""Answer option CRUD routes nested under questions (API_SPEC.md §9)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentAdmin, RequestId, get_db
from app.schemas.answer_option import (
    AnswerOptionCreateRequest,
    AnswerOptionDeleteData,
    AnswerOptionListData,
    AnswerOptionResponseData,
    AnswerOptionUpdateRequest,
)
from app.schemas.common import DataResponse, Meta
from app.services.answer_option_service import AnswerOptionService

router = APIRouter(
    prefix="/quizzes/{quiz_id}/sections/{section_id}/questions/{question_id}/options",
)


def get_answer_option_service(db: Annotated[Session, Depends(get_db)]) -> AnswerOptionService:
    return AnswerOptionService(db)


AnswerOptionServiceDep = Annotated[AnswerOptionService, Depends(get_answer_option_service)]


def _option_response(option) -> AnswerOptionResponseData:
    return AnswerOptionResponseData.model_validate(option)


def _envelope(data, request_id: str, *, status_code: int = status.HTTP_200_OK) -> JSONResponse:
    payload = DataResponse(data=data, meta=Meta(request_id=request_id))
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


@router.post(
    "",
    response_model=DataResponse[AnswerOptionResponseData],
    status_code=status.HTTP_201_CREATED,
    summary="Create answer option",
)
def create_answer_option(
    quiz_id: UUID,
    section_id: UUID,
    question_id: UUID,
    body: AnswerOptionCreateRequest,
    admin: CurrentAdmin,
    service: AnswerOptionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    option = service.create(quiz_id, section_id, question_id, body, owner_id=admin.id)
    return _envelope(
        _option_response(option),
        request_id,
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "",
    response_model=DataResponse[AnswerOptionListData],
    status_code=status.HTTP_200_OK,
    summary="List answer options",
)
def list_answer_options(
    quiz_id: UUID,
    section_id: UUID,
    question_id: UUID,
    admin: CurrentAdmin,
    service: AnswerOptionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    items, total = service.list(quiz_id, section_id, question_id, owner_id=admin.id)
    data = AnswerOptionListData(
        items=[_option_response(o) for o in items],
        total=total,
    )
    return _envelope(data, request_id)


@router.get(
    "/{option_id}",
    response_model=DataResponse[AnswerOptionResponseData],
    status_code=status.HTTP_200_OK,
    summary="Get answer option",
)
def get_answer_option(
    quiz_id: UUID,
    section_id: UUID,
    question_id: UUID,
    option_id: UUID,
    admin: CurrentAdmin,
    service: AnswerOptionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    option = service.get(quiz_id, section_id, question_id, option_id, owner_id=admin.id)
    return _envelope(_option_response(option), request_id)


@router.patch(
    "/{option_id}",
    response_model=DataResponse[AnswerOptionResponseData],
    status_code=status.HTTP_200_OK,
    summary="Update answer option",
)
def update_answer_option(
    quiz_id: UUID,
    section_id: UUID,
    question_id: UUID,
    option_id: UUID,
    body: AnswerOptionUpdateRequest,
    admin: CurrentAdmin,
    service: AnswerOptionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    option = service.update(quiz_id, section_id, question_id, option_id, body, owner_id=admin.id)
    return _envelope(_option_response(option), request_id)


@router.delete(
    "/{option_id}",
    response_model=DataResponse[AnswerOptionDeleteData],
    status_code=status.HTTP_200_OK,
    summary="Delete answer option",
)
def delete_answer_option(
    quiz_id: UUID,
    section_id: UUID,
    question_id: UUID,
    option_id: UUID,
    admin: CurrentAdmin,
    service: AnswerOptionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    service.delete(quiz_id, section_id, question_id, option_id, owner_id=admin.id)
    return _envelope(AnswerOptionDeleteData(id=option_id, deleted=True), request_id)
