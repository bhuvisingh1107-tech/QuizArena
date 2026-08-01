"""Structured logging configuration (NFR-063)."""

import logging
import sys
from typing import Any

from app.config import Settings


class JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter for production stdout capture."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            payload["requestId"] = getattr(record, "request_id")
        if hasattr(record, "audit_event"):
            payload["event"] = getattr(record, "audit_event")
        for key in (
            "method",
            "path",
            "status_code",
            "duration_ms",
            "client_ip",
            "app_env",
            "debug",
            "room_id",
            "quiz_id",
            "participant_id",
            "admin_username",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True, default=str)


def configure_logging(settings: Settings) -> None:
    """Configure root logger with JSON or text formatting."""
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            ),
        )

    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.debug else logging.WARNING,
    )
    logging.getLogger("quizarena.audit").setLevel(logging.INFO)
