"""Administrator authentication service (SYSTEM_ARCHITECTURE.md §5.1)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import AuthenticationError, ValidationError
from app.core.password_policy import validate_password_policy
from app.core.security import (
    TokenValidationError,
    create_access_token,
    hash_password,
    validate_access_token,
    verify_password,
)
from app.models.admin import Admin
from app.models.enums import SecurityEventType
from app.repositories.admin_repository import AdminRepository
from app.repositories.security_log_repository import SecurityLogRepository


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    expires_at: datetime


@dataclass(frozen=True)
class RequestContext:
    """Optional request metadata for security logging (no secrets)."""

    ip_address: str | None = None
    user_agent: str | None = None


class AuthService:
    """Admin login, logout, and JWT validation."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._admins = AdminRepository(session)
        self._security_logs = SecurityLogRepository(session)

    def login(
        self,
        username: str,
        password: str,
        *,
        context: RequestContext | None = None,
    ) -> LoginResult:
        """Verify credentials, issue JWT, and log the security event."""
        context = context or RequestContext()
        admin = self._admins.get_by_username(username)

        if admin is None or not verify_password(password, admin.password_hash):
            self._security_logs.create(
                event_type=SecurityEventType.LOGIN_FAILED,
                username=username,
                message="Invalid username or password",
                ip_address=context.ip_address,
                user_agent=context.user_agent,
            )
            self._session.commit()
            raise AuthenticationError(
                "INVALID_CREDENTIALS",
                "Invalid username or password",
            )

        token, expires_at = create_access_token(
            subject=admin.id,
            role=admin.role.value,
            settings=self._settings,
        )
        self._security_logs.create(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            username=admin.username,
            message="Administrator logged in",
            ip_address=context.ip_address,
            user_agent=context.user_agent,
        )
        self._session.commit()
        return LoginResult(access_token=token, expires_at=expires_at)

    def logout(
        self,
        admin: Admin,
        *,
        context: RequestContext | None = None,
    ) -> None:
        """Log logout security event. Client discards the JWT (stateless v1)."""
        context = context or RequestContext()
        self._security_logs.create(
            event_type=SecurityEventType.LOGOUT,
            username=admin.username,
            message="Administrator logged out",
            ip_address=context.ip_address,
            user_agent=context.user_agent,
        )
        self._session.commit()

    def get_admin_from_token(self, token: str) -> Admin:
        """Validate JWT and load the corresponding Admin row."""
        try:
            claims = validate_access_token(token, self._settings)
        except TokenValidationError as exc:
            raise AuthenticationError(exc.code, exc.message) from exc

        role = claims.get("role")
        if role != "admin":
            raise AuthenticationError("AUTH_ERROR", "Invalid authentication token")

        try:
            admin_id = UUID(str(claims["sub"]))
        except (KeyError, ValueError, TypeError) as exc:
            raise AuthenticationError("AUTH_ERROR", "Invalid authentication token") from exc

        admin = self._admins.get_by_id(admin_id)
        if admin is None:
            raise AuthenticationError("AUTH_ERROR", "Invalid authentication token")
        return admin

    def change_password(
        self,
        admin: Admin,
        *,
        current_password: str,
        new_password: str,
    ) -> None:
        """Verify current password, enforce FR-005 policy, and update hash."""
        if not verify_password(current_password, admin.password_hash):
            raise AuthenticationError(
                "INVALID_CREDENTIALS",
                "Current password is incorrect",
            )
        validate_password_policy(new_password)
        if verify_password(new_password, admin.password_hash):
            raise ValidationError(
                "PASSWORD_UNCHANGED",
                "New password must be different from the current password",
            )
        self._admins.update_password_hash(admin, hash_password(new_password))
        self._session.commit()
