"""HTTP middleware: CORS, request ID, and error handling."""

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings
from app.core.exceptions import QuizArenaError

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


def setup_cors(app: FastAPI, settings: Settings) -> None:
    """Configure CORS for allowed frontend origins."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a correlation ID to every request for structured logging."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _error_envelope(
    code: str,
    message: str,
    request_id: str,
    *,
    details: list[Any] | None = None,
    status_code: int = 500,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
            },
            "meta": {"requestId": request_id},
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Map domain and validation exceptions to the standard error envelope."""

    @app.exception_handler(QuizArenaError)
    async def quizarena_error_handler(request: Request, exc: QuizArenaError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.warning(
            "Domain error: %s",
            exc.code,
            extra={"request_id": request_id},
        )
        return _error_envelope(
            exc.code,
            exc.message,
            request_id,
            details=exc.details,
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return _error_envelope(
            "VALIDATION_ERROR",
            "Request validation failed",
            request_id,
            details=exc.errors(),
            status_code=422,
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_handler(
        request: Request,
        exc: PydanticValidationError,
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return _error_envelope(
            "VALIDATION_ERROR",
            "Request validation failed",
            request_id,
            details=exc.errors(),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        logger.exception(
            "Unhandled exception",
            extra={"request_id": request_id},
        )
        return _error_envelope(
            "INTERNAL_ERROR",
            "An unexpected error occurred",
            request_id,
            status_code=500,
        )


def setup_middleware(app: FastAPI, settings: Settings) -> None:
    """Register all HTTP middleware and exception handlers."""
    setup_cors(app, settings)
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
