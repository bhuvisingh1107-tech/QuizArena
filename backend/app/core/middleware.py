"""HTTP middleware: CORS, security headers, request ID, body limits, access logs."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import Settings
from app.core.exceptions import QuizArenaError

logger = logging.getLogger(__name__)
access_logger = logging.getLogger("quizarena.access")

REQUEST_ID_HEADER = "X-Request-ID"


def setup_cors(app: FastAPI, settings: Settings) -> None:
    """Configure CORS for allowed frontend origins."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            REQUEST_ID_HEADER,
            "X-Requested-With",
        ],
        expose_headers=[REQUEST_ID_HEADER, "Content-Disposition"],
        max_age=600,
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security headers to every response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        # HSTS is typically terminated at the reverse proxy; set only when HTTPS is clear.
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


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


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies early (media uploads share this ceiling)."""

    def __init__(self, app, max_body_bytes: int) -> None:
        super().__init__(app)
        self._max_body_bytes = max_body_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                length = 0
            if length > self._max_body_bytes:
                return PlainTextResponse("Request entity too large", status_code=413)
        return await call_next(request)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Structured access log for non-health traffic."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        path = request.url.path
        if path.endswith("/health") or path.endswith("/ready") or path.endswith("/live"):
            return response
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        client = request.client.host if request.client else None
        access_logger.info(
            "%s %s -> %s",
            request.method,
            path,
            response.status_code,
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "method": request.method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": client,
            },
        )
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


def register_exception_handlers(app: FastAPI, settings: Settings) -> None:
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
            "Unhandled exception: %s: %s",
            type(exc).__name__,
            exc,
            extra={"request_id": request_id},
        )
        # Never expose Python tracebacks or raw exception text to clients.
        return _error_envelope(
            "INTERNAL_ERROR",
            "An unexpected error occurred. Please try again.",
            request_id,
            details=[{"requestId": request_id}],
            status_code=500,
        )


def setup_middleware(app: FastAPI, settings: Settings) -> None:
    """Register all HTTP middleware and exception handlers."""
    # Starlette applies middleware in reverse add order for request path.
    setup_cors(app, settings)
    if settings.trusted_hosts and settings.trusted_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware, max_body_bytes=settings.max_request_body_bytes)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app, settings)
