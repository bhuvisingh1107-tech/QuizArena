"""Centralized structured audit logging for operational events."""

from __future__ import annotations

import logging
from typing import Any

audit_logger = logging.getLogger("quizarena.audit")


def audit(event: str, *, level: int = logging.INFO, **fields: Any) -> None:
    """Emit a structured audit log line (JSON formatter picks up extras)."""
    extra = {"audit_event": event, **{k: v for k, v in fields.items() if v is not None}}
    audit_logger.log(level, event, extra=extra)
