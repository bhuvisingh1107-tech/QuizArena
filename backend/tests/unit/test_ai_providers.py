"""AI provider presets, resolution, and fail-fast config checks."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.core.exceptions import ValidationError as DomainValidationError
from app.services.ai.provider import get_ai_provider
from app.services.ai.provider_presets import (
    ai_configuration_error,
    resolve_ai_runtime,
)
from app.services.ai.providers.anthropic import AnthropicProvider
from app.services.ai.providers.openai_compatible import OpenAICompatibleProvider


def test_resolve_openrouter_preset() -> None:
    settings = Settings(
        ai_provider="openrouter",
        ai_api_key="sk-or-test",
        app_env="development",
    )
    runtime = resolve_ai_runtime(settings)
    assert runtime.base_url == "https://openrouter.ai/api/v1"
    assert runtime.chat_model.startswith("openai/")
    assert runtime.extra_headers.get("X-Title") == "QuizArena"
    assert runtime.requires_api_key is True


def test_resolve_gemini_preset() -> None:
    runtime = resolve_ai_runtime(
        Settings(ai_provider="gemini", ai_api_key="gm-test", app_env="development"),
    )
    assert "generativelanguage.googleapis.com" in runtime.base_url
    assert "aiplatform.googleapis.com" not in runtime.base_url  # not Vertex
    assert runtime.transport == "gemini"
    assert runtime.chat_model == "gemini-2.5-flash"
    assert runtime.embedding_model == "gemini-embedding-001"


def test_get_provider_gemini_uses_native_client() -> None:
    from app.services.ai.providers.gemini import GeminiProvider

    provider = get_ai_provider(
        Settings(
            ai_provider="gemini",
            ai_api_key="AQtest",
            ai_chat_model="gemini-2.5-flash",
            app_env="development",
        ),
    )
    assert isinstance(provider, GeminiProvider)
    assert provider._generate_url() == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent"
    )
    assert provider._headers.get("x-goog-api-key") == "AQtest"
    assert "Authorization" not in provider._headers



def test_resolve_ollama_allows_empty_key() -> None:
    runtime = resolve_ai_runtime(Settings(ai_provider="ollama", ai_api_key="", app_env="development"))
    assert runtime.requires_api_key is False
    assert runtime.base_url.endswith(":11434/v1")
    assert ai_configuration_error(
        Settings(ai_provider="ollama", ai_api_key="", app_env="development"),
    ) is None


def test_resolve_anthropic_uses_native_transport() -> None:
    runtime = resolve_ai_runtime(
        Settings(ai_provider="anthropic", ai_api_key="sk-ant", app_env="development"),
    )
    assert runtime.transport == "anthropic"
    assert runtime.force_local_embeddings is True


def test_get_provider_openai() -> None:
    provider = get_ai_provider(
        Settings(
            ai_provider="openai",
            ai_api_key="sk-test",
            app_env="development",
        ),
    )
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.name == "openai"


def test_get_provider_anthropic() -> None:
    provider = get_ai_provider(
        Settings(
            ai_provider="anthropic",
            ai_api_key="sk-ant",
            app_env="development",
        ),
    )
    assert isinstance(provider, AnthropicProvider)


def test_mock_blocked_outside_test() -> None:
    with pytest.raises(DomainValidationError) as exc:
        get_ai_provider(Settings(ai_provider="mock", app_env="development"))
    assert exc.value.code == "AI_CONFIG_ERROR"


def test_missing_key_blocked_for_openai() -> None:
    with pytest.raises(DomainValidationError) as exc:
        get_ai_provider(
            Settings(ai_provider="openai", ai_api_key="", app_env="development"),
        )
    assert exc.value.code == "AI_CONFIG_ERROR"


def test_production_settings_require_ai() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(
            app_env="production",
            debug=False,
            jwt_secret_key="a-strong-production-secret-key",
            database_url="postgresql://u:p@db.example/quizarena?sslmode=require",
            cors_origins=["https://app.vercel.app"],
            trusted_hosts=["api.example.onrender.com"],
            public_app_url="https://app.vercel.app",
            ai_provider="mock",
        )
    assert "AI_PROVIDER" in str(exc.value) or "AI quiz generation" in str(exc.value)


def test_production_settings_accept_openai() -> None:
    settings = Settings(
        app_env="production",
        debug=False,
        jwt_secret_key="a-strong-production-secret-key",
        database_url="postgresql://u:p@db.example/quizarena?sslmode=require",
        cors_origins=["https://app.vercel.app"],
        trusted_hosts=["api.example.onrender.com"],
        public_app_url="https://app.vercel.app",
        ai_provider="openai",
        ai_api_key="sk-live-test",
    )
    assert ai_configuration_error(settings) is None


def test_mock_ok_in_test_env() -> None:
    provider = get_ai_provider(Settings(ai_provider="mock", app_env="test"))
    assert provider.name == "mock"
