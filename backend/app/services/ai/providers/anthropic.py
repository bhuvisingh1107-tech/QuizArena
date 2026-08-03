"""Anthropic Messages API provider (chat) + local embeddings."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import ValidationError
from app.services.ai.local_embeddings import hash_embeddings
from app.services.ai.provider import AiProvider, ChatMessage, parse_json_object
from app.services.ai.provider_presets import resolve_ai_runtime

logger = logging.getLogger(__name__)


class AnthropicProvider(AiProvider):
    """Native Anthropic Messages API — used when AI_PROVIDER=anthropic."""

    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        runtime = resolve_ai_runtime(settings)
        if not runtime.api_key:
            raise ValidationError(
                "AI_CONFIG_ERROR",
                "AI_API_KEY is required when AI_PROVIDER=anthropic",
            )
        self._settings = settings
        self._runtime = runtime
        self._base = runtime.base_url.rstrip("/")
        self._headers = {
            "x-api-key": runtime.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def chat_json(self, messages: list[ChatMessage], *, temperature: float = 0.3) -> dict[str, Any]:
        system_parts = [m.content for m in messages if m.role == "system"]
        user_messages = [
            {"role": m.role if m.role in {"user", "assistant"} else "user", "content": m.content}
            for m in messages
            if m.role != "system"
        ]
        if not user_messages:
            user_messages = [{"role": "user", "content": "Return a JSON object."}]

        payload: dict[str, Any] = {
            "model": self._runtime.chat_model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": user_messages,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        prompt_chars = sum(len(m.content) for m in messages)
        logger.info(
            "LLM request provider=anthropic model=%s messages=%s prompt_chars=%s",
            self._runtime.chat_model,
            len(messages),
            prompt_chars,
        )

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self._base}/v1/messages",
                headers=self._headers,
                json=payload,
            )
        if response.status_code >= 400:
            logger.error(
                "Anthropic request failed status=%s body=%s",
                response.status_code,
                response.text[:500],
            )
            raise ValidationError(
                "AI_PROVIDER_ERROR",
                "The Anthropic API rejected the request. Check AI_API_KEY and AI_CHAT_MODEL.",
                details=[{"status": response.status_code}],
            )

        data = response.json()
        try:
            blocks = data.get("content") or []
            text_parts = [
                str(block.get("text") or "")
                for block in blocks
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            content = "\n".join(part for part in text_parts if part)
        except (AttributeError, TypeError) as exc:
            raise ValidationError(
                "AI_PROVIDER_ERROR",
                "Unexpected Anthropic Messages payload.",
            ) from exc

        logger.info(
            "LLM response chars=%s preview=%s",
            len(content),
            (content[:500] + "…") if len(content) > 500 else content,
        )
        try:
            parsed = parse_json_object(content)
        except Exception as exc:
            logger.exception("Anthropic JSON parse failed")
            raise ValidationError(
                "AI_PARSE_ERROR",
                "The AI returned invalid JSON. Generation will retry or fail.",
            ) from exc
        return parsed

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Anthropic has no public embeddings API; store local vectors for chunk metadata.
        logger.info("Anthropic embeddings: using local hash vectors count=%s", len(texts))
        return hash_embeddings(texts)
