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
            raise self._http_error(response, url=url, model=self._model, operation="generateContent")

        data = response.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(str(part.get("text") or "") for part in parts if isinstance(part, dict))
        except (KeyError, IndexError, TypeError) as exc:
            logger.error(
                "Unexpected Gemini payload url=%s model=%s status=%s headers=%s body=%s",
                url,
                self._model,
                response.status_code,
                dict(response.headers),
                response.text,
            )
            raise ValidationError(
                "AI_PROVIDER_ERROR",
                f"Unexpected generateContent payload from Gemini. Raw body: {response.text}",
                details=[
                    {
                        "url": url,
                        "model": self._model,
                        "status": response.status_code,
                        "headers": self._safe_headers(response),
                        "body": response.text,
                        "bodyJson": data if isinstance(data, dict) else None,
                    },
                ],
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
                    logger.error(
                        "Gemini embedContent failed url=%s model=%s status=%s headers=%s body=%s",
                        url,
                        embed_model,
                        response.status_code,
                        self._safe_headers(response),
                        response.text,
                    )
                    logger.warning("Falling back to local hash embeddings after embedContent failure")
                    return hash_embeddings(texts)
                data = response.json()
                values = (data.get("embedding") or {}).get("values") or []
                vectors.append([float(v) for v in values])
        return vectors

    @staticmethod
    def _safe_headers(response: httpx.Response) -> dict[str, str]:
        """Loggable response headers (never echo the API key)."""
        out: dict[str, str] = {}
        for key, value in response.headers.items():
            if key.lower() in {"x-goog-api-key", "authorization"}:
                out[key] = "***redacted***"
            else:
                out[key] = value
        return out

    def _http_error(
        self,
        response: httpx.Response,
        *,
        url: str,
        model: str,
        operation: str,
    ) -> ValidationError:
        """Build an error that preserves Google's full HTTP body (no generic rewrite)."""
        body_text = response.text
        headers = self._safe_headers(response)
        body_json: Any | None = None
        google_message = body_text
        google_status: str | None = None
        try:
            body_json = response.json()
            err = body_json.get("error") if isinstance(body_json, dict) else None
            if isinstance(err, dict):
                google_message = str(err.get("message") or body_text)
                if err.get("status") is not None:
                    google_status = str(err.get("status"))
                elif err.get("code") is not None:
                    google_status = str(err.get("code"))
        except Exception:
            body_json = None

        logger.error(
            "Gemini %s failed url=%s model=%s status=%s google_status=%s headers=%s body=%s",
            operation,
            url,
            model,
            response.status_code,
            google_status,
            headers,
            body_text,
        )

        # Message shown in UI / job.error_message — must be Google's text, not a generic phrase.
        message = (
            f"Gemini {operation} HTTP {response.status_code}"
            + (f" ({google_status})" if google_status else "")
            + f": {google_message}"
        )
        return ValidationError(
            "AI_PROVIDER_ERROR",
            message,
            details=[
                {
                    "url": url,
                    "model": model,
                    "operation": operation,
                    "status": response.status_code,
                    "headers": headers,
                    "body": body_text,
                    "bodyJson": body_json,
                },
            ],
        )
