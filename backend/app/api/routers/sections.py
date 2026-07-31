"""Section CRUD routes nested under quizzes (API_SPEC.md §9)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentAdmin, RequestId, get_db
from app.schemas.common import DataResponse, Meta
from app.schemas.section import (
    SectionCreateRequest,
    SectionDeleteData,
    SectionListData,
    SectionResponseData,
    SectionUpdateRequest,
)
from app.services.section_service import SectionService

router = APIRouter(prefix="/quizzes/{quiz_id}/sections")


def get_section_service(db: Annotated[Session, Depends(get_db)]) -> SectionService:
    return SectionService(db)


SectionServiceDep = Annotated[SectionService, Depends(get_section_service)]


def _section_response(section) -> SectionResponseData:
    return SectionResponseData.model_validate(section)


def _envelope(data, request_id: str, *, status_code: int = status.HTTP_200_OK) -> JSONResponse:
    payload = DataResponse(data=data, meta=Meta(request_id=request_id))
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


@router.post(
    "",
    response_model=DataResponse[SectionResponseData],
    status_code=status.HTTP_201_CREATED,
    summary="Create section",
)
def create_section(
    quiz_id: UUID,
    body: SectionCreateRequest,
    _: CurrentAdmin,
    service: SectionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    section = service.create(quiz_id, body)
    return _envelope(
        _section_response(section),
        request_id,
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "",
    response_model=DataResponse[SectionListData],
    status_code=status.HTTP_200_OK,
    summary="List sections for a quiz",
)
def list_sections(
    quiz_id: UUID,
    _: CurrentAdmin,
    service: SectionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    items, total = service.list(quiz_id)
    data = SectionListData(
        items=[_section_response(s) for s in items],
        total=total,
    )
    return _envelope(data, request_id)


@router.get(
    "/{section_id}",
    response_model=DataResponse[SectionResponseData],
    status_code=status.HTTP_200_OK,
    summary="Get section",
)
def get_section(
    quiz_id: UUID,
    section_id: UUID,
    _: CurrentAdmin,
    service: SectionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    section = service.get(quiz_id, section_id)
    return _envelope(_section_response(section), request_id)


@router.patch(
    "/{section_id}",
    response_model=DataResponse[SectionResponseData],
    status_code=status.HTTP_200_OK,
    summary="Update section",
)
def update_section(
    quiz_id: UUID,
    section_id: UUID,
    body: SectionUpdateRequest,
    _: CurrentAdmin,
    service: SectionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    section = service.update(quiz_id, section_id, body)
    return _envelope(_section_response(section), request_id)


@router.delete(
    "/{section_id}",
    response_model=DataResponse[SectionDeleteData],
    status_code=status.HTTP_200_OK,
    summary="Delete section",
)
def delete_section(
    quiz_id: UUID,
    section_id: UUID,
    _: CurrentAdmin,
    service: SectionServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    service.delete(quiz_id, section_id)
    return _envelope(SectionDeleteData(id=section_id, deleted=True), request_id)
