"""JWT issuance/validation and password hashing utilities."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from passlib.context import CryptContext

from app.config import Settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt. Never store the plaintext."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(
    *,
    subject: UUID | str,
    role: str,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> tuple[str, datetime]:
    """Create a signed JWT and return (token, expires_at UTC).

    Claims (SYSTEM_ARCHITECTURE.md §5.1):
      sub  — administrator id
      iat  — issued-at
      exp  — expiration
      role — ``admin`` in v1
    """
    now = datetime.now(UTC)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(hours=settings.jwt_expiry_hours)
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "role": role,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)
    return token, expires_at


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Decode and validate a JWT. Raises jose exceptions on failure."""
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[ALGORITHM],
        options={"require_sub": True, "require_exp": True, "require_iat": True},
    )


class TokenValidationError(Exception):
    """Raised when a JWT is missing, expired, or otherwise invalid."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def validate_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Validate JWT and return claims, mapping jose errors to TokenValidationError."""
    try:
        return decode_access_token(token, settings)
    except ExpiredSignatureError as exc:
        raise TokenValidationError("AUTH_ERROR", "Token has expired") from exc
    except JWTError as exc:
        raise TokenValidationError("AUTH_ERROR", "Invalid authentication token") from exc
