"""Password policy helpers (FR-005)."""

import re

from app.core.exceptions import ValidationError

_MIN_LENGTH = 8
_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"[0-9]")
_SPECIAL = re.compile(r"[^A-Za-z0-9]")


def validate_password_policy(password: str) -> None:
    """Enforce FR-005 strong password requirements.

    Minimum 8 characters with uppercase, lowercase, numeric, and special character.
    """
    errors: list[dict[str, str]] = []
    if len(password) < _MIN_LENGTH:
        errors.append(
            {
                "field": "password",
                "message": f"Password must be at least {_MIN_LENGTH} characters",
            },
        )
    if not _UPPER.search(password):
        errors.append({"field": "password", "message": "Password must include an uppercase letter"})
    if not _LOWER.search(password):
        errors.append({"field": "password", "message": "Password must include a lowercase letter"})
    if not _DIGIT.search(password):
        errors.append({"field": "password", "message": "Password must include a digit"})
    if not _SPECIAL.search(password):
        errors.append(
            {"field": "password", "message": "Password must include a special character"},
        )
    if errors:
        raise ValidationError(
            "PASSWORD_POLICY_VIOLATION",
            "Password does not meet complexity requirements",
            details=errors,
        )
