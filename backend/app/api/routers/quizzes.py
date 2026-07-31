"""Quiz CRUD routes (API_SPEC.md §8)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentAdmin, RequestId, get_db
from app.models.enums import QuizStatus
from app.schemas.common import DataResponse, Meta
from app.schemas.quiz import (
    QuizCreateRequest,
    QuizDeleteData,
    QuizListData,
    QuizResponseData,
    QuizUpdateRequest,
)
from app.services.quiz_service import QuizService

router = APIRouter()


def get_quiz_service(db: Annotated[Session, Depends(get_db)]) -> QuizService:
    return QuizService(db)


QuizServiceDep = Annotated[QuizService, Depends(get_quiz_service)]


def _quiz_response(quiz) -> QuizResponseData:
    return QuizResponseData.model_validate(quiz)


def _envelope(data, request_id: str, *, status_code: int = status.HTTP_200_OK) -> JSONResponse:
    payload = DataResponse(data=data, meta=Meta(request_id=request_id))
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


@router.post(
    "",
    response_model=DataResponse[QuizResponseData],
    status_code=status.HTTP_201_CREATED,
    summary="Create quiz",
)
def create_quiz(
    body: QuizCreateRequest,
    _: CurrentAdmin,
    service: QuizServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    """Create a Draft quiz with default configuration."""
    quiz = service.create(body)
    return _envelope(_quiz_response(quiz), request_id, status_code=status.HTTP_201_CREATED)


@router.get(
    "",
    response_model=DataResponse[QuizListData],
    status_code=status.HTTP_200_OK,
    summary="List quizzes",
)
def list_quizzes(
    _: CurrentAdmin,
    service: QuizServiceDep,
    request_id: RequestId,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[
        QuizStatus | None,
        Query(alias="status", description="Filter by quiz status"),
    ] = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
) -> JSONResponse:
    """Paginated quiz library with optional title search and status filter."""
    items, total = service.list(
        offset=offset,
        limit=limit,
        status=status_filter,
        search=search,
    )
    data = QuizListData(
        items=[_quiz_response(q) for q in items],
        total=total,
        offset=offset,
        limit=limit,
    )
    has_more = offset + len(items) < total
    payload = DataResponse(
        data=data,
        meta=Meta(request_id=request_id, has_more=has_more),
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


@router.get(
    "/{quiz_id}",
    response_model=DataResponse[QuizResponseData],
    status_code=status.HTTP_200_OK,
    summary="Get quiz by ID",
)
def get_quiz(
    quiz_id: UUID,
    _: CurrentAdmin,
    service: QuizServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    quiz = service.get(quiz_id)
    return _envelope(_quiz_response(quiz), request_id)


@router.patch(
    "/{quiz_id}",
    response_model=DataResponse[QuizResponseData],
    status_code=status.HTTP_200_OK,
    summary="Update quiz",
)
def update_quiz(
    quiz_id: UUID,
    body: QuizUpdateRequest,
    _: CurrentAdmin,
    service: QuizServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    quiz = service.update(quiz_id, body)
    return _envelope(_quiz_response(quiz), request_id)


@router.delete(
    "/{quiz_id}",
    response_model=DataResponse[QuizDeleteData],
    status_code=status.HTTP_200_OK,
    summary="Delete quiz",
)
def delete_quiz(
    quiz_id: UUID,
    _: CurrentAdmin,
    service: QuizServiceDep,
    request_id: RequestId,
    hard: Annotated[
        bool,
        Query(description="Permanently remove the quiz (hard delete)"),
    ] = False,
) -> JSONResponse:
    """Soft-delete by default (status=Deleted). Blocked when InUse."""
    quiz = service.delete(quiz_id, hard=hard)
    data = QuizDeleteData(
        id=quiz_id,
        deleted=True,
        hard=hard,
        status=None if hard else (quiz.status if quiz else None),
    )
    return _envelope(data, request_id)
