"""Question CRUD routes nested under quiz sections (API_SPEC.md §9)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentAdmin, RequestId, get_db
from app.schemas.common import DataResponse, Meta
from app.schemas.question import (
    QuestionCreateRequest,
    QuestionDeleteData,
    QuestionListData,
    QuestionResponseData,
    QuestionUpdateRequest,
)
from app.services.question_service import QuestionService

router = APIRouter(prefix="/quizzes/{quiz_id}/sections/{section_id}/questions")


def get_question_service(db: Annotated[Session, Depends(get_db)]) -> QuestionService:
    return QuestionService(db)


QuestionServiceDep = Annotated[QuestionService, Depends(get_question_service)]


def _question_response(question) -> QuestionResponseData:
    return QuestionResponseData.model_validate(question)


def _envelope(data, request_id: str, *, status_code: int = status.HTTP_200_OK) -> JSONResponse:
    payload = DataResponse(data=data, meta=Meta(request_id=request_id))
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


@router.post(
    "",
    response_model=DataResponse[QuestionResponseData],
    status_code=status.HTTP_201_CREATED,
    summary="Create question",
)
def create_question(
    quiz_id: UUID,
    section_id: UUID,
    body: QuestionCreateRequest,
    _: CurrentAdmin,
    service: QuestionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    question = service.create(quiz_id, section_id, body)
    return _envelope(
        _question_response(question),
        request_id,
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "",
    response_model=DataResponse[QuestionListData],
    status_code=status.HTTP_200_OK,
    summary="List questions for a section",
)
def list_questions(
    quiz_id: UUID,
    section_id: UUID,
    _: CurrentAdmin,
    service: QuestionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    items, total = service.list(quiz_id, section_id)
    data = QuestionListData(
        items=[_question_response(q) for q in items],
        total=total,
    )
    return _envelope(data, request_id)


@router.get(
    "/{question_id}",
    response_model=DataResponse[QuestionResponseData],
    status_code=status.HTTP_200_OK,
    summary="Get question",
)
def get_question(
    quiz_id: UUID,
    section_id: UUID,
    question_id: UUID,
    _: CurrentAdmin,
    service: QuestionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    question = service.get(quiz_id, section_id, question_id)
    return _envelope(_question_response(question), request_id)


@router.patch(
    "/{question_id}",
    response_model=DataResponse[QuestionResponseData],
    status_code=status.HTTP_200_OK,
    summary="Update question",
)
def update_question(
    quiz_id: UUID,
    section_id: UUID,
    question_id: UUID,
    body: QuestionUpdateRequest,
    _: CurrentAdmin,
    service: QuestionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    question = service.update(quiz_id, section_id, question_id, body)
    return _envelope(_question_response(question), request_id)


@router.delete(
    "/{question_id}",
    response_model=DataResponse[QuestionDeleteData],
    status_code=status.HTTP_200_OK,
    summary="Delete question",
)
def delete_question(
    quiz_id: UUID,
    section_id: UUID,
    question_id: UUID,
    _: CurrentAdmin,
    service: QuestionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    service.delete(quiz_id, section_id, question_id)
    return _envelope(QuestionDeleteData(id=question_id, deleted=True), request_id)
