"""Abstract AI provider — OpenAI / OpenRouter / Gemini / Anthropic / Ollama / mock."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.core.exceptions import ValidationError
from app.services.ai.provider_presets import ai_configuration_error, resolve_ai_runtime

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    role: str
    content: str


class AiProvider(ABC):
    """Provider-agnostic chat + embeddings interface."""

    name: str = "abstract"

    @abstractmethod
    def chat_json(self, messages: list[ChatMessage], *, temperature: float = 0.3) -> dict[str, Any]:
        """Return parsed JSON object from a chat completion."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors aligned with ``texts``."""


_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    match = _JSON_FENCE.search(text)
    if match:
        text = match.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("AI response JSON must be an object")
    return data


def render_template(template: str, **values: object) -> str:
    out = template
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out


def _settings_with_provider(settings: Settings, provider: str) -> Settings:
    """Return settings with ``ai_provider`` overridden (pydantic model_copy)."""
    return settings.model_copy(update={"ai_provider": provider})


def get_ai_provider(settings: Settings) -> AiProvider:
    """Resolve provider. Mock is blocked outside automated tests."""
    effective = settings

    # Prefer a real LLM whenever a key is configured (except explicit test mock).
    if (
        settings.ai_provider == "mock"
        and settings.app_env != "test"
        and settings.ai_api_key.strip()
    ):
        logger.warning(
            "AI_PROVIDER=mock overridden to openai because AI_API_KEY is set",
        )
        effective = _settings_with_provider(settings, "openai")

    if effective.app_env != "test":
        error = ai_configuration_error(effective)
        if error:
            raise ValidationError("AI_CONFIG_ERROR", error)

    runtime = resolve_ai_runtime(effective)

    if runtime.transport == "mock":
        from app.services.ai.providers.mock import MockAiProvider

        logger.info("AI provider selected=mock (test-only)")
        return MockAiProvider(effective)

    if runtime.transport == "anthropic":
        from app.services.ai.providers.anthropic import AnthropicProvider

        logger.info(
            "AI provider selected=anthropic model=%s base=%s",
            runtime.chat_model,
            runtime.base_url,
        )
        return AnthropicProvider(effective)

    if runtime.transport == "gemini":
        # Optional alternate provider — production default is OpenAI Chat Completions.
        from app.services.ai.providers.gemini import GeminiProvider

        logger.info(
            "AI provider selected=gemini model=%s base=%s",
            runtime.chat_model,
            runtime.base_url,
        )
        return GeminiProvider(effective)

    from app.services.ai.providers.openai_compatible import OpenAICompatibleProvider

    logger.info(
        "AI provider selected=%s transport=openai_compatible model=%s base=%s",
        runtime.provider,
        runtime.chat_model,
        runtime.base_url,
    )
    return OpenAICompatibleProvider(effective, runtime=runtime)
