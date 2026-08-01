"""Settings validation for production and Neon URL normalization."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_normalizes_postgres_scheme_to_postgresql() -> None:
    settings = Settings(
        database_url="postgres://user:pass@ep-x.us-west-2.aws.neon.tech/neondb?sslmode=require",
        jwt_secret_key="dev-only",
    )
    assert settings.database_url.startswith("postgresql://")
    assert settings.is_postgres is True
    assert "sslmode=require" in settings.database_url


def test_production_rejects_sqlite() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            debug=False,
            jwt_secret_key="a-strong-production-secret-key",
            database_url="sqlite:///./quizarena.db",
            cors_origins=["https://app.vercel.app"],
        )


def test_production_accepts_postgres() -> None:
    settings = Settings(
        app_env="production",
        debug=False,
        jwt_secret_key="a-strong-production-secret-key",
        database_url="postgresql://u:p@db.example/quizarena?sslmode=require",
        cors_origins=["https://app.vercel.app"],
        trusted_hosts=["api.example.onrender.com"],
    )
    assert settings.is_postgres is True
