"""Admin dashboard routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import CurrentAdmin, RequestId, get_db
from app.schemas.common import DataResponse, Meta
from app.schemas.dashboard import DashboardSummaryData
from app.services.dashboard_service import DashboardService

router = APIRouter()


def get_dashboard_service(db: Annotated[Session, Depends(get_db)]) -> DashboardService:
    return DashboardService(db)


DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]


@router.get(
    "/summary",
    response_model=DataResponse[DashboardSummaryData],
    status_code=status.HTTP_200_OK,
    summary="Admin dashboard summary",
)
def dashboard_summary(
    _: CurrentAdmin,
    service: DashboardServiceDep,
    request_id: RequestId,
) -> JSONResponse:
    data = service.summary()
    payload = DataResponse(data=data, meta=Meta(request_id=request_id))
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
