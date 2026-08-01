"""Health, readiness, and liveness probes."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession, RequestId, check_database_connection
from app.api.websocket.connection_manager import connection_manager
from app.config import get_settings
from app.schemas.common import DataResponse, HealthData, Meta

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])

_STARTED_AT = time.monotonic()


@router.get(
    "/live",
    summary="Liveness probe",
    description="Process is up (no dependency checks).",
)
def liveness() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "alive",
            "uptimeSeconds": round(time.monotonic() - _STARTED_AT, 1),
        },
    )


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Ready to accept traffic when the database is reachable.",
)
def readiness(db: DbSession, request_id: RequestId) -> JSONResponse:
    try:
        check_database_connection(db)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "database": "connected",
                "meta": {"requestId": request_id},
            },
        )
    except SQLAlchemyError:
        logger.exception("Readiness check failed", extra={"request_id": request_id})
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": "disconnected",
                "meta": {"requestId": request_id},
            },
        )


@router.get(
    "/health",
    response_model=DataResponse[HealthData],
    summary="Health check probe",
    description="Service status, database connectivity, and WebSocket pool summary.",
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

    rooms = connection_manager.snapshot_counts()
    settings = get_settings()
    payload = {
        "data": {
            "status": overall_status,
            "database": database_status,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "appEnv": settings.app_env,
            "websocket": {
                "activeRooms": rooms["activeRooms"],
                "connections": rooms["connections"],
            },
            "uptimeSeconds": round(time.monotonic() - _STARTED_AT, 1),
        },
        "meta": {"requestId": request_id},
    }
    return JSONResponse(status_code=http_status, content=payload)


@router.get(
    "/metrics",
    summary="Lightweight performance metrics",
    description="JSON metrics suitable for basic monitoring scrapers.",
)
def metrics() -> JSONResponse:
    rooms = connection_manager.snapshot_counts()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "uptimeSeconds": round(time.monotonic() - _STARTED_AT, 1),
            "websocket": rooms,
        },
    )
