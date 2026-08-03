"""Google AI Studio Gemini provider via native generateContent (not Vertex, not OpenAI-compat)."""

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


class GeminiProvider(AiProvider):
    """Google AI Studio REST: ``x-goog-api-key`` + ``:generateContent``.

    Endpoint host: ``generativelanguage.googleapis.com`` (AI Studio).
    Not Vertex AI (``*-aiplatform.googleapis.com``).
    """

    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        runtime = resolve_ai_runtime(settings)
        if not runtime.api_key:
            raise ValidationError(
                "AI_CONFIG_ERROR",
                "AI_API_KEY is required when AI_PROVIDER=gemini",
            )
        self._settings = settings
        self._runtime = runtime
        self._api_key = runtime.api_key.strip()
        self._model = runtime.chat_model.strip()
        # Native base is the Generative Language API root (strip /openai if present).
        base = runtime.base_url.rstrip("/")
        if base.endswith("/openai"):
            base = base[: -len("/openai")]
        if "/v1beta" not in base:
            base = "https://generativelanguage.googleapis.com/v1beta"
        self._base = base.rstrip("/")
        self._headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

    def _generate_url(self) -> str:
        return f"{self._base}/models/{self._model}:generateContent"

    def chat_json(self, messages: list[ChatMessage], *, temperature: float = 0.3) -> dict[str, Any]:
        system_parts = [m.content for m in messages if m.role == "system"]
        contents: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == "system":
                continue
            role = "model" if msg.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg.content}]})
        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Return a JSON object."}]}]

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }
        if system_parts:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}],
            }

        url = self._generate_url()
        prompt_chars = sum(len(m.content) for m in messages)
        logger.info(
            "LLM request provider=gemini transport=generateContent url=%s model=%s "
            "messages=%s prompt_chars=%s auth=x-goog-api-key",
            url,
            self._model,
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
            response = client.post(url, headers=self._headers, json=payload)

        if response.status_code >= 400:
            body = response.text[:2000]
            logger.error(
                "Gemini generateContent failed status=%s url=%s model=%s body=%s",
                response.status_code,
                url,
                self._model,
                body,
            )
            raise ValidationError(
                "AI_PROVIDER_ERROR",
                "The AI provider rejected the request. Check AI_API_KEY and AI_CHAT_MODEL.",
                details=[
                    {
                        "status": response.status_code,
                        "url": url,
                        "model": self._model,
                        "auth": "x-goog-api-key",
                        "body": body,
                    },
                ],
            )

        data = response.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Unexpected Gemini payload keys=%s", list(data.keys()) if isinstance(data, dict) else type(data))
            raise ValidationError(
                "AI_PROVIDER_ERROR",
                "Unexpected generateContent payload from Gemini.",
                details=[{"body": str(data)[:1000]}],
            ) from exc

        logger.info(
            "LLM response chars=%s preview=%s",
            len(text),
            (text[:500] + "…") if len(text) > 500 else text,
        )
        try:
            parsed = parse_json_object(text)
        except Exception as exc:
            logger.exception("Gemini JSON parse failed")
            raise ValidationError(
                "AI_PARSE_ERROR",
                "The AI returned invalid JSON. Generation will retry or fail.",
            ) from exc
        return parsed

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._runtime.force_local_embeddings:
            return hash_embeddings(texts)

        embed_model = self._runtime.embedding_model.strip() or "gemini-embedding-001"
        url = f"{self._base}/models/{embed_model}:embedContent"
        vectors: list[list[float]] = []
        with httpx.Client(timeout=120.0) as client:
            for text in texts:
                response = client.post(
                    url,
                    headers=self._headers,
                    json={"content": {"parts": [{"text": text}]}},
                )
                if response.status_code >= 400:
                    logger.warning(
                        "Gemini embedContent failed status=%s body=%s; using local hash",
                        response.status_code,
                        response.text[:500],
                    )
                    return hash_embeddings(texts)
                data = response.json()
                values = (data.get("embedding") or {}).get("values") or []
                vectors.append([float(v) for v in values])
        return vectors
