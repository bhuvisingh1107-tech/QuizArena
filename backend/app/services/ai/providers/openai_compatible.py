"""OpenAI Chat Completions + embeddings (OpenAI, OpenRouter, Ollama, gateways)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import ValidationError
from app.services.ai.local_embeddings import hash_embeddings
from app.services.ai.provider import AiProvider, ChatMessage, parse_json_object
from app.services.ai.provider_presets import ResolvedAiRuntime, resolve_ai_runtime

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(AiProvider):
    name = "openai_compatible"

    def __init__(
        self,
        settings: Settings,
        *,
        runtime: ResolvedAiRuntime | None = None,
    ) -> None:
        self._settings = settings
        self._runtime = runtime or resolve_ai_runtime(settings)
        self.name = self._runtime.provider
        if self._runtime.requires_api_key and not self._runtime.api_key:
            raise ValidationError(
                "AI_CONFIG_ERROR",
                f"AI_API_KEY is required when AI_PROVIDER={self._runtime.provider}",
            )
        self._base = self._runtime.base_url.rstrip("/")
        self._headers = {
            "Content-Type": "application/json",
            **self._runtime.extra_headers,
        }
        # Ollama accepts any/empty key; other gateways need Bearer.
        key = self._runtime.api_key or "ollama"
        self._headers["Authorization"] = f"Bearer {key}"

    def chat_json(self, messages: list[ChatMessage], *, temperature: float = 0.3) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._runtime.chat_model,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if self._runtime.use_json_response_format:
            payload["response_format"] = {"type": "json_object"}

        prompt_chars = sum(len(m.content) for m in messages)
        logger.info(
            "LLM request provider=%s model=%s base=%s messages=%s prompt_chars=%s",
            self._runtime.provider,
            self._runtime.chat_model,
            self._base,
            len(messages),
            prompt_chars,
        )
        for msg in messages:
            logger.info(
                "LLM prompt role=%s preview=%s",
                msg.role,
                (msg.content[:400] + "…") if len(msg.content) > 400 else msg.content,
            )

        data = self._post_chat(payload)
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

    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self._base}/chat/completions",
                headers=self._headers,
                json=payload,
            )
        # Some Ollama builds reject response_format; retry once without it.
        if (
            response.status_code >= 400
            and "response_format" in payload
            and self._runtime.provider == "ollama"
        ):
            logger.warning(
                "%s rejected response_format; retrying without json_object mode",
                self._runtime.provider,
            )
            retry_payload = {k: v for k, v in payload.items() if k != "response_format"}
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self._base}/chat/completions",
                    headers=self._headers,
                    json=retry_payload,
                )
        if response.status_code >= 400:
            body = response.text[:8000]
            url = f"{self._base}/chat/completions"
            logger.error(
                "LLM request failed status=%s url=%s model=%s body=%s",
                response.status_code,
                url,
                payload.get("model"),
                body,
            )
            # Prefer upstream message when the provider returns JSON; never invent a
            # provider-specific rewrite for OpenAI Chat Completions.
            message = (
                f"Chat Completions HTTP {response.status_code} for model "
                f"{payload.get('model')}: {body}"
            )
            try:
                err = response.json().get("error")
                if isinstance(err, dict) and err.get("message"):
                    message = (
                        f"Chat Completions HTTP {response.status_code}: {err['message']}"
                    )
                elif isinstance(err, str) and err.strip():
                    message = f"Chat Completions HTTP {response.status_code}: {err}"
            except Exception:
                pass
            raise ValidationError(
                "AI_PROVIDER_ERROR",
                message,
                details=[
                    {
                        "status": response.status_code,
                        "url": url,
                        "model": payload.get("model"),
                        "body": body,
                    },
                ],
                status_code=400 if response.status_code < 500 else 502,
            )
        return response.json()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._runtime.force_local_embeddings:
            logger.info(
                "Embeddings: local hash vectors provider=%s count=%s",
                self._runtime.provider,
                len(texts),
            )
            return hash_embeddings(texts)

        payload = {
            "model": self._runtime.embedding_model,
            "input": texts,
        }
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self._base}/embeddings",
                headers=self._headers,
                json=payload,
            )
        if response.status_code >= 400:
            logger.warning(
                "Remote embeddings failed status=%s; falling back to local hash vectors",
                response.status_code,
            )
            return hash_embeddings(texts)
        data = response.json()
        items = sorted(data.get("data") or [], key=lambda row: row.get("index", 0))
        return [list(item.get("embedding") or []) for item in items]
