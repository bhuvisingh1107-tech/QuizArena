"""CORS exact origins + Vercel preview Origin regex."""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import DEFAULT_CORS_ORIGIN_REGEX, Settings
from app.core.middleware import setup_cors


def _cors_app(settings: Settings) -> TestClient:
    app = FastAPI()
    setup_cors(app, settings)

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "1"}

    @app.post("/api/v1/auth/login")
    def login() -> dict[str, str]:
        return {"token": "x"}

    return TestClient(app)


def test_default_regex_allows_vercel_production_and_preview() -> None:
    pattern = re.compile(DEFAULT_CORS_ORIGIN_REGEX)
    assert pattern.fullmatch("https://quiz-arena-zeta-six.vercel.app")
    assert pattern.fullmatch(
        "https://quiz-arena-r2bdnened-bhuvisingh1107-techs-projects.vercel.app",
    )
    assert pattern.fullmatch("https://quiz-arena-git-feat-user.vercel.app")


def test_default_regex_rejects_non_vercel_and_http() -> None:
    pattern = re.compile(DEFAULT_CORS_ORIGIN_REGEX)
    assert pattern.fullmatch("http://quiz-arena-zeta-six.vercel.app") is None
    assert pattern.fullmatch("https://evil.com") is None
    assert pattern.fullmatch("https://vercel.app.evil.com") is None
    assert pattern.fullmatch("https://example.com") is None


def test_preflight_allows_exact_localhost_with_credentials() -> None:
    settings = Settings(
        cors_origins=["http://localhost:5173"],
        cors_origin_regex="",
        jwt_secret_key="dev",
    )
    client = _cors_app(settings)
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_preflight_allows_vercel_preview_via_regex() -> None:
    preview = "https://quiz-arena-r2bdnened-bhuvisingh1107-techs-projects.vercel.app"
    settings = Settings(
        cors_origins=["https://quiz-arena-zeta-six.vercel.app"],
        cors_origin_regex=DEFAULT_CORS_ORIGIN_REGEX,
        jwt_secret_key="dev",
    )
    client = _cors_app(settings)
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": preview,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == preview
    assert response.headers["access-control-allow-credentials"] == "true"


def test_preflight_rejects_unknown_origin() -> None:
    settings = Settings(
        cors_origins=["https://quiz-arena-zeta-six.vercel.app"],
        cors_origin_regex=DEFAULT_CORS_ORIGIN_REGEX,
        jwt_secret_key="dev",
    )
    client = _cors_app(settings)
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_simple_get_reflects_preview_origin() -> None:
    preview = "https://quiz-arena-git-branch-team.vercel.app"
    settings = Settings(
        cors_origins=["http://localhost:5173"],
        cors_origin_regex=DEFAULT_CORS_ORIGIN_REGEX,
        jwt_secret_key="dev",
    )
    client = _cors_app(settings)
    response = client.get("/ping", headers={"Origin": preview})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == preview
    assert response.headers["access-control-allow-credentials"] == "true"


def test_production_rejects_wildcard_cors_regex() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            debug=False,
            jwt_secret_key="a-strong-production-secret-key",
            database_url="postgresql://u:p@db.example/quizarena?sslmode=require",
            cors_origins=["https://quiz-arena-zeta-six.vercel.app"],
            cors_origin_regex=".*",
            trusted_hosts=["api.example.onrender.com"],
            public_app_url="https://quiz-arena-zeta-six.vercel.app",
        )


def test_production_accepts_default_vercel_regex() -> None:
    settings = Settings(
        app_env="production",
        debug=False,
        jwt_secret_key="a-strong-production-secret-key",
        database_url="postgresql://u:p@db.example/quizarena?sslmode=require",
        cors_origins=["https://quiz-arena-zeta-six.vercel.app"],
        trusted_hosts=["api.example.onrender.com"],
        public_app_url="https://quiz-arena-zeta-six.vercel.app",
    )
    assert settings.cors_origin_regex == DEFAULT_CORS_ORIGIN_REGEX
    assert settings.cors_origin_regex_or_none == DEFAULT_CORS_ORIGIN_REGEX
