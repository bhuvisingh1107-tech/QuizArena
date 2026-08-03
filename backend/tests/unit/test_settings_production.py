"""Settings validation for production and Neon URL normalization."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


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
        cors_origins=["https://app.vercel.app/"],
        trusted_hosts=["api.example.onrender.com"],
        public_app_url="https://app.vercel.app/",
        ai_provider="openai",
        ai_api_key="sk-test-key",
    )
    assert settings.is_postgres is True
    assert settings.cors_origins == ["https://app.vercel.app"]
    assert settings.public_app_url == "https://app.vercel.app"


def test_production_accepts_localhost_public_app_url() -> None:
    """Initial deploys may point PUBLIC_APP_URL at the local Vite origin."""
    settings = Settings(
        app_env="production",
        debug=False,
        jwt_secret_key="a-strong-production-secret-key",
        database_url="postgresql://u:p@db.example/quizarena?sslmode=require",
        cors_origins=["http://localhost:5173"],
        trusted_hosts=["api.example.onrender.com"],
        public_app_url="http://localhost:5173",
        ai_provider="openai",
        ai_api_key="sk-test-key",
    )
    assert settings.public_app_url == "http://localhost:5173"


def test_production_rejects_blank_or_relative_public_app_url() -> None:
    for bad in ("", "   ", "/join", "app.vercel.app", "ftp://example.com"):
        with pytest.raises(ValidationError):
            Settings(
                app_env="production",
                debug=False,
                jwt_secret_key="a-strong-production-secret-key",
                database_url="postgresql://u:p@db.example/quizarena?sslmode=require",
                cors_origins=["https://app.vercel.app"],
                trusted_hosts=["api.example.onrender.com"],
                public_app_url=bad,
                ai_provider="openai",
                ai_api_key="sk-test-key",
            )


def test_production_requires_trusted_hosts() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            debug=False,
            jwt_secret_key="a-strong-production-secret-key",
            database_url="postgresql://u:p@db.example/quizarena?sslmode=require",
            cors_origins=["https://app.vercel.app"],
            trusted_hosts=["*"],
            public_app_url="https://app.vercel.app",
            ai_provider="openai",
            ai_api_key="sk-test-key",
        )


def test_env_csv_cors_and_trusted_hosts_without_json() -> None:
    """Render-style CSV env vars must not fail pydantic JSON decoding."""
    get_settings.cache_clear()
    env = {
        "APP_ENV": "production",
        "DEBUG": "false",
        "JWT_SECRET_KEY": "a-strong-production-secret-key",
        "DATABASE_URL": "postgresql://u:p@db.example/quizarena?sslmode=require",
        "CORS_ORIGINS": "https://app.vercel.app,https://preview.vercel.app",
        "TRUSTED_HOSTS": "api.example.onrender.com,localhost",
        "PUBLIC_APP_URL": "https://app.vercel.app",
        "AI_PROVIDER": "openai",
        "AI_API_KEY": "sk-test-key",
    }
    with patch.dict(os.environ, env, clear=False):
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.cors_origins == [
        "https://app.vercel.app",
        "https://preview.vercel.app",
    ]
    assert settings.trusted_hosts == ["api.example.onrender.com", "localhost"]
    get_settings.cache_clear()


def test_env_json_array_cors_still_supported() -> None:
    settings = Settings(
        cors_origins='["https://a.example","https://b.example/"]',
        trusted_hosts='["api.example"]',
    )
    assert settings.cors_origins == ["https://a.example", "https://b.example"]
    assert settings.trusted_hosts == ["api.example"]
