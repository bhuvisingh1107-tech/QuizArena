"""Health check endpoint (API_SPEC.md §15, NFR-062)."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession, RequestId, check_database_connection
from app.schemas.common import DataResponse, HealthData, Meta

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=DataResponse[HealthData],
    summary="Health check probe",
    description="Returns service status and database connectivity (Render health probe).",
)
def health_check(db: DbSession, request_id: RequestId) -> JSONResponse:
    """Public health endpoint at GET /api/v1/health."""
    database_status = "connected"
    http_status = status.HTTP_200_OK
    overall_status = "healthy"

    try:
        check_database_connection(db)
    except SQLAlchemyError:
        logger.exception("Database health check failed", extra={"request_id": request_id})
        database_status = "disconnected"
        overall_status = "unhealthy"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    payload = DataResponse[HealthData](
        data=HealthData(
            status=overall_status,
            database=database_status,
            timestamp=datetime.now(UTC),
        ),
        meta=Meta(request_id=request_id),
    )
    return JSONResponse(
        status_code=http_status,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
