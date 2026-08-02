"""Tests for production-safe initial admin bootstrap."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.core.security import hash_password, verify_password
from app.models import Base
from app.models.admin import Admin
from app.repositories.admin_repository import AdminRepository
from app.services.auth_service import AuthService

BOOTSTRAP_PASSWORD = "BootstrapPass1!"
BOOTSTRAP_USERNAME = "bootstrap_admin"


@pytest.fixture()
def empty_session() -> Generator[Session, None, None]:
    """In-memory DB with schema only — no seeded admin."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "jwt_secret_key": "test-secret-key-for-jwt-signing",
        "admin_username": BOOTSTRAP_USERNAME,
        "admin_password": BOOTSTRAP_PASSWORD,
        "admin_password_hash": "",
        "trusted_hosts": ["*"],
        "cors_origins": ["http://localhost:5173"],
    }
    values.update(overrides)
    return Settings.model_construct(**values)


def _admin_count(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(Admin)) or 0)


def test_bootstrap_empty_database_creates_admin(
    empty_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = AuthService(empty_session, _settings())
    with caplog.at_level("INFO"):
        created = service.ensure_bootstrap_admin()

    assert created is True
    assert _admin_count(empty_session) == 1
    admin = AdminRepository(empty_session).get_by_username(BOOTSTRAP_USERNAME)
    assert admin is not None
    assert verify_password(BOOTSTRAP_PASSWORD, admin.password_hash)
    assert "Created initial admin." in caplog.text


def test_bootstrap_existing_admin_is_unchanged(
    empty_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    original_hash = hash_password("OriginalPassw0rd!")
    AdminRepository(empty_session).create(
        username="existing",
        password_hash=original_hash,
        name="Existing Host",
    )
    empty_session.commit()

    service = AuthService(
        empty_session,
        _settings(admin_username="other_admin", admin_password="OtherPassw0rd!"),
    )
    with caplog.at_level("INFO"):
        created = service.ensure_bootstrap_admin()

    assert created is False
    assert _admin_count(empty_session) == 1
    admin = AdminRepository(empty_session).get_by_username("existing")
    assert admin is not None
    assert admin.password_hash == original_hash
    assert AdminRepository(empty_session).get_by_username("other_admin") is None
    assert "Admin already exists." in caplog.text
    assert "Created initial admin." not in caplog.text


def test_bootstrap_repeated_startup_is_idempotent(
    empty_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = AuthService(empty_session, _settings())

    with caplog.at_level("INFO"):
        assert service.ensure_bootstrap_admin() is True
        assert service.ensure_bootstrap_admin() is False
        assert service.ensure_bootstrap_admin() is False

    assert _admin_count(empty_session) == 1
    assert caplog.text.count("Created initial admin.") == 1
    assert caplog.text.count("Admin already exists.") == 2


def test_bootstrap_requires_password_when_empty(
    empty_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = AuthService(
        empty_session,
        _settings(admin_password="", admin_password_hash=""),
    )
    with caplog.at_level("WARNING"):
        created = service.ensure_bootstrap_admin()
    assert created is False
    assert _admin_count(empty_session) == 0
    assert "Bootstrap admin skipped" in caplog.text


def test_bootstrap_invalid_password_does_not_raise(
    empty_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Weak ADMIN_PASSWORD must not crash startup when no admin exists."""
    service = AuthService(
        empty_session,
        _settings(admin_password="weak"),
    )
    with caplog.at_level("WARNING"):
        created = service.ensure_bootstrap_admin()
    assert created is False
    assert _admin_count(empty_session) == 0
    assert "Bootstrap admin skipped" in caplog.text
    assert "Password does not meet complexity requirements" in caplog.text


def test_bootstrap_skips_password_check_when_admin_exists(
    empty_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    AdminRepository(empty_session).create(
        username="existing",
        password_hash=hash_password("OriginalPassw0rd!"),
        name="Existing Host",
    )
    empty_session.commit()

    service = AuthService(
        empty_session,
        _settings(admin_password="weak"),
    )
    with caplog.at_level("INFO"):
        created = service.ensure_bootstrap_admin()
    assert created is False
    assert "Admin already exists." in caplog.text
    assert "Bootstrap admin skipped" not in caplog.text
