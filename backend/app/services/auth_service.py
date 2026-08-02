"""Host authentication service (SYSTEM_ARCHITECTURE.md §5.1)."""

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.exceptions import AuthenticationError, ConflictError, ValidationError
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

logger = logging.getLogger(__name__)


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
    """Host login, registration, logout, and JWT validation."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._admins = AdminRepository(session)
        self._security_logs = SecurityLogRepository(session)

    def ensure_bootstrap_admin(self) -> bool:
        """Create the initial host admin when the database has none.

        Uses ``ADMIN_USERNAME`` / ``ADMIN_PASSWORD`` from settings.
        Never updates an existing password. Safe to call on every startup.

        Returns:
            True if a new admin was created, False if one already existed.
        """
        if self._admins.exists_any():
            logger.info("Admin already exists.")
            return False

        username = (self._settings.admin_username or "admin").strip() or "admin"
        plaintext = (self._settings.admin_password or "").strip()
        password_hash = (self._settings.admin_password_hash or "").strip()

        if plaintext:
            validate_password_policy(plaintext)
            password_hash = hash_password(plaintext)
        elif not password_hash:
            raise RuntimeError(
                "No admin exists and ADMIN_PASSWORD is not set. "
                "Set ADMIN_USERNAME and ADMIN_PASSWORD (or ADMIN_PASSWORD_HASH) "
                "so startup can create the initial admin.",
            )

        try:
            self._admins.create(
                username=username,
                password_hash=password_hash,
                name="Host",
            )
            self._session.commit()
        except IntegrityError:
            # Concurrent worker won the race — treat as already bootstrapped.
            self._session.rollback()
            logger.info("Admin already exists.")
            return False

        logger.info("Created initial admin.")
        return True

    def register(
        self,
        *,
        name: str,
        email: str,
        username: str,
        password: str,
        context: RequestContext | None = None,
    ) -> LoginResult:
        """Create a host account and issue a JWT."""
        context = context or RequestContext()
        validate_password_policy(password)

        if self._admins.get_by_username(username) is not None:
            raise ConflictError("USERNAME_TAKEN", "That username is already taken")
        if self._admins.get_by_email(email) is not None:
            raise ConflictError("EMAIL_TAKEN", "That email is already registered")

        admin = self._admins.create(
            username=username,
            password_hash=hash_password(password),
            name=name,
            email=email,
        )
        token, expires_at = create_access_token(
            subject=admin.id,
            role=admin.role.value,
            settings=self._settings,
        )
        self._security_logs.create(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            username=admin.username,
            message="Host registered and signed in",
            ip_address=context.ip_address,
            user_agent=context.user_agent,
        )
        self._session.commit()
        return LoginResult(access_token=token, expires_at=expires_at)

    def login(
        self,
        username: str,
        password: str,
        *,
        context: RequestContext | None = None,
    ) -> LoginResult:
        """Verify credentials (username or email), issue JWT, and log the event."""
        context = context or RequestContext()
        logger.info("login: lookup start")
        admin = self._admins.get_by_username_or_email(username)
        logger.info("login: lookup done found=%s", admin is not None)

        logger.info("login: verify_password start")
        password_ok = admin is not None and verify_password(password, admin.password_hash)
        logger.info("login: verify_password done ok=%s", password_ok)

        if admin is None or not password_ok:
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

        logger.info("login: create_access_token start")
        token, expires_at = create_access_token(
            subject=admin.id,
            role=admin.role.value,
            settings=self._settings,
        )
        logger.info("login: create_access_token done")
        self._security_logs.create(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            username=admin.username,
            message="Host logged in",
            ip_address=context.ip_address,
            user_agent=context.user_agent,
        )
        logger.info("login: security_log commit start")
        self._session.commit()
        logger.info("login: security_log commit done")
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
            message="Host logged out",
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
