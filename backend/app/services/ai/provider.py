"""Abstract AI provider — swap OpenAI / Anthropic / Gemini / local later."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.config import Settings


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


def get_ai_provider(settings: Settings) -> AiProvider:
    logger = logging.getLogger(__name__)
    if settings.ai_provider == "openai_compatible":
        from app.services.ai.providers.openai_compatible import OpenAICompatibleProvider

        logger.info(
            "AI provider selected=openai_compatible model=%s base=%s",
            settings.ai_chat_model,
            settings.ai_api_base_url,
        )
        return OpenAICompatibleProvider(settings)
    from app.services.ai.providers.mock import MockAiProvider

    logger.info("AI provider selected=mock")
    return MockAiProvider(settings)
