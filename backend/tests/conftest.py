"""Pytest configuration and shared fixtures."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.api.websocket.connection_manager import connection_manager
from app.config import Settings, get_settings
from app.core.rate_limit import join_rate_limiter, login_rate_limiter
from app.core.security import hash_password
from app.main import create_app
from app.models import Base
from app.models.admin import Admin

TEST_PASSWORD = "AdminPassw0rd!"
TEST_USERNAME = "admin"


@pytest.fixture(autouse=True)
def _reset_rate_limiters() -> None:
    login_rate_limiter.reset()
    join_rate_limiter.reset()
    connection_manager.reset()


@pytest.fixture(autouse=True)
def _auto_progression_isolation(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Keep live auto-timers from interfering with most tests; always cancel leftover tasks."""
    monkeypatch.setattr(
        "app.services.quiz_execution_service.DEFAULT_LIVE_QUESTION_SECONDS",
        3600,
    )
    monkeypatch.setattr("app.services.timer_service.DEFAULT_QUESTION_SECONDS", 3600)
    monkeypatch.setattr("app.services.timer_service.REVEAL_DWELL_SECONDS", 0.05)
    yield
    from app.services.timer_service import auto_progression

    for room_id in list(auto_progression._tasks):
        auto_progression.cancel_room(room_id)


@pytest.fixture()
def test_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-jwt-signing")
    monkeypatch.setenv("JWT_EXPIRY_HOURS", "8")
    monkeypatch.setenv("LOG_FORMAT", "text")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("TRUSTED_HOSTS", "test,testserver,localhost,127.0.0.1")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173,http://test")
    get_settings.cache_clear()
    settings = get_settings()
    yield settings
    get_settings.cache_clear()


@pytest.fixture()
def db_session(test_settings: Settings) -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    session = factory()
    admin = Admin(
        username=TEST_USERNAME,
        password_hash=hash_password(TEST_PASSWORD),
        name="Test Host",
        email="admin@example.com",
    )
    session.add(admin)
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session, test_settings: Settings) -> Generator[TestClient, None, None]:
    import app.api.deps as api_deps

    engine = db_session.get_bind()
    api_deps._engine = engine  # type: ignore[assignment]
    api_deps._session_factory = sessionmaker(  # type: ignore[assignment]
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    app = create_app()

    def _override_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    api_deps._engine = None
    api_deps._session_factory = None


@pytest.fixture()
def admin_token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/admin/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["accessToken"]
