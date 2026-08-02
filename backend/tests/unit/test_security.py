"""Unit tests for password hashing and JWT utilities."""

from datetime import timedelta
from uuid import uuid4

import pytest
from jose import jwt

from app.config import Settings
from app.core.password_policy import validate_password_policy
from app.core.exceptions import ValidationError
from app.core.security import (
    ALGORITHM,
    TokenValidationError,
    create_access_token,
    hash_password,
    validate_access_token,
    verify_password,
)


def test_password_hash_and_verify() -> None:
    hashed = hash_password("AdminPassw0rd!")
    assert hashed != "AdminPassw0rd!"
    assert verify_password("AdminPassw0rd!", hashed)
    assert not verify_password("wrong", hashed)


def test_password_policy_rejects_weak() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_password_policy("short")
    assert exc.value.code == "PASSWORD_POLICY_VIOLATION"


def test_password_policy_rejects_under_eight_chars() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_password_policy("Ab1!xyz")  # 7 chars, otherwise complex
    assert exc.value.code == "PASSWORD_POLICY_VIOLATION"
    assert any("at least 8 characters" in d.get("message", "").lower() for d in exc.value.details)


def test_password_policy_accepts_eight_char_minimum() -> None:
    validate_password_policy("Abcd1!xy")


def test_password_policy_accepts_strong() -> None:
    validate_password_policy("AdminPassw0rd!")


def test_create_and_validate_token(test_settings: Settings) -> None:
    admin_id = uuid4()
    token, expires_at = create_access_token(
        subject=admin_id,
        role="admin",
        settings=test_settings,
    )
    claims = validate_access_token(token, test_settings)
    assert claims["sub"] == str(admin_id)
    assert claims["role"] == "admin"
    assert expires_at.tzinfo is not None


def test_expired_token_rejected(test_settings: Settings) -> None:
    token, _ = create_access_token(
        subject=uuid4(),
        role="admin",
        settings=test_settings,
        expires_delta=timedelta(seconds=-5),
    )
    with pytest.raises(TokenValidationError) as exc:
        validate_access_token(token, test_settings)
    assert exc.value.code == "AUTH_ERROR"
    assert "expired" in exc.value.message.lower()


def test_invalid_token_rejected(test_settings: Settings) -> None:
    with pytest.raises(TokenValidationError):
        validate_access_token("not.a.jwt", test_settings)


def test_tampered_token_rejected(test_settings: Settings) -> None:
    token, _ = create_access_token(
        subject=uuid4(),
        role="admin",
        settings=test_settings,
    )
    parts = token.split(".")
    # Corrupt payload segment
    bad = f"{parts[0]}.{parts[1][:-2]}xx.{parts[2]}"
    with pytest.raises(TokenValidationError):
        validate_access_token(bad, test_settings)


def test_wrong_secret_rejected(test_settings: Settings) -> None:
    token = jwt.encode(
        {"sub": str(uuid4()), "role": "admin", "exp": 9999999999, "iat": 1},
        "other-secret",
        algorithm=ALGORITHM,
    )
    with pytest.raises(TokenValidationError):
        validate_access_token(token, test_settings)
