"""Security audit log data access."""

from sqlalchemy.orm import Session

from app.models.enums import SecurityEventType
from app.models.security_log import SecurityLog


class SecurityLogRepository:
    """Repository for authentication security events (FR-008)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        event_type: SecurityEventType,
        username: str | None = None,
        message: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SecurityLog:
        entry = SecurityLog(
            event_type=event_type,
            username=username,
            message=message,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._session.add(entry)
        self._session.flush()
        return entry
