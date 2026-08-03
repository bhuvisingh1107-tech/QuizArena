"""OpenAI-compatible chat + embeddings provider (OpenAI, Azure, local gateways)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import ValidationError
from app.services.ai.provider import AiProvider, ChatMessage, parse_json_object

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(AiProvider):
    name = "openai_compatible"

    def __init__(self, settings: Settings) -> None:
        if not settings.ai_api_key.strip():
            raise ValidationError(
                "AI_CONFIG_ERROR",
                "AI_API_KEY is required when AI_PROVIDER=openai_compatible",
            )
        self._settings = settings
        self._base = settings.ai_api_base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {settings.ai_api_key}",
            "Content-Type": "application/json",
        }

    def chat_json(self, messages: list[ChatMessage], *, temperature: float = 0.3) -> dict[str, Any]:
        payload = {
            "model": self._settings.ai_chat_model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        prompt_chars = sum(len(m.content) for m in messages)
        logger.info(
            "LLM request provider=openai_compatible model=%s messages=%s prompt_chars=%s",
            self._settings.ai_chat_model,
            len(messages),
            prompt_chars,
        )
        for msg in messages:
            logger.info(
                "LLM prompt role=%s preview=%s",
                msg.role,
                (msg.content[:400] + "…") if len(msg.content) > 400 else msg.content,
            )

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self._base}/chat/completions",
                headers=self._headers,
                json=payload,
            )
        if response.status_code >= 400:
            logger.error(
                "LLM request failed status=%s body=%s",
                response.status_code,
                response.text[:500],
            )
            raise ValidationError(
                "AI_PROVIDER_ERROR",
                "The AI provider rejected the request. Check AI_API_KEY and model settings.",
                details=[{"status": response.status_code}],
            )
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValidationError(
                "AI_PROVIDER_ERROR",
                "Unexpected chat completion payload from the AI provider.",
            ) from exc

        raw = str(content)
        logger.info(
            "LLM response chars=%s preview=%s",
            len(raw),
            (raw[:500] + "…") if len(raw) > 500 else raw,
        )
        try:
            parsed = parse_json_object(raw)
        except Exception as exc:
            logger.exception("LLM JSON parse failed")
            raise ValidationError(
                "AI_PARSE_ERROR",
                "The AI returned invalid JSON. Generation will retry or fail.",
            ) from exc
        logger.info("LLM parsed JSON keys=%s", sorted(parsed.keys()))
        return parsed

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {
            "model": self._settings.ai_embedding_model,
            "input": texts,
        }
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self._base}/embeddings",
                headers=self._headers,
                json=payload,
            )
        if response.status_code >= 400:
            raise ValidationError(
                "AI_PROVIDER_ERROR",
                f"Embeddings failed ({response.status_code})",
                details=[response.text[:500]],
            )
        data = response.json()
        items = sorted(data.get("data") or [], key=lambda row: row.get("index", 0))
        return [list(item.get("embedding") or []) for item in items]
