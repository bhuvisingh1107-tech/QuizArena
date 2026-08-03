"""Gemini native provider error surfacing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.config import Settings
from app.core.exceptions import ValidationError
from app.services.ai.provider import ChatMessage
from app.services.ai.providers.gemini import GeminiProvider


def _settings() -> Settings:
    return Settings(
        ai_provider="gemini",
        ai_api_key="test-gemini-key",
        ai_chat_model="gemini-2.5-flash",
        ai_embedding_model="gemini-embedding-001",
        app_env="development",
        _env_file=None,
    )


def test_gemini_http_error_includes_full_google_body() -> None:
    provider = GeminiProvider(_settings())
    google_body = {
        "error": {
            "code": 400,
            "message": "API key not valid. Please pass a valid API key.",
            "status": "INVALID_ARGUMENT",
            "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID"}],
        }
    }
    response = httpx.Response(
        400,
        json=google_body,
        headers={"content-type": "application/json", "x-goog-api-key": "should-redact"},
        request=httpx.Request("POST", provider._generate_url()),
    )

    with patch("app.services.ai.providers.gemini.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        client.post.return_value = response
        client_cls.return_value = client

        with pytest.raises(ValidationError) as exc_info:
            provider.chat_json(
                [
                    ChatMessage(role="system", content="Return JSON"),
                    ChatMessage(role="user", content="{}"),
                ]
            )

    err = exc_info.value
    assert err.code == "AI_PROVIDER_ERROR"
    assert "The AI provider rejected the request" not in err.message
    assert "API key not valid" in err.message
    assert "INVALID_ARGUMENT" in err.message
    assert "HTTP 400" in err.message
    detail = err.details[0]
    assert detail["url"].endswith("gemini-2.5-flash:generateContent")
    assert detail["model"] == "gemini-2.5-flash"
    assert detail["status"] == 400
    assert detail["bodyJson"]["error"]["message"].startswith("API key not valid")
    assert "API key not valid" in detail["body"]
    assert detail["headers"].get("x-goog-api-key") == "***redacted***"
