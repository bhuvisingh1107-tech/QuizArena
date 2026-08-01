"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import api_router
from app.api.websocket import heartbeat_monitor, websocket_router
from app.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import setup_middleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    from app.services.timer_service import auto_progression

    settings = get_settings()
    configure_logging(settings)
    logger.info(
        "Starting QuizArena API",
        extra={"app_env": settings.app_env, "debug": settings.debug},
    )
    await auto_progression.start()
    if settings.app_env != "test":
        await heartbeat_monitor.start()
    try:
        yield
    finally:
        await auto_progression.stop()
        if settings.app_env != "test":
            await heartbeat_monitor.stop()
        logger.info("Shutting down QuizArena API")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="QuizArena API",
        version="1.0.0",
        description="Real-time quiz platform REST API and WebSocket server.",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    setup_middleware(app, settings)

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(websocket_router)

    return app


app = create_app()
