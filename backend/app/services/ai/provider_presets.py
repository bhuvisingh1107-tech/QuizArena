"""Named AI provider presets (OpenAI, OpenRouter, Gemini, Anthropic, Ollama)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AiProviderName = Literal[
    "mock",
    "openai_compatible",
    "openai",
    "openrouter",
    "gemini",
    "anthropic",
    "ollama",
]

REAL_AI_PROVIDERS: frozenset[str] = frozenset(
    {
        "openai_compatible",
        "openai",
        "openrouter",
        "gemini",
        "anthropic",
        "ollama",
    },
)

DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"


@dataclass(frozen=True)
class ProviderPreset:
    """Defaults applied when ``AI_PROVIDER`` is a named alias."""

    transport: Literal["openai_compatible", "anthropic", "gemini"]
    base_url: str
    default_chat_model: str
    default_embedding_model: str
    requires_api_key: bool
    extra_headers: dict[str, str]
    # When True, use local hash embeddings (Anthropic has no embeddings API).
    force_local_embeddings: bool = False
    # Prefer omitting response_format=json_object (some Ollama builds reject it).
    prefer_json_response_format: bool = True


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "openai": ProviderPreset(
        transport="openai_compatible",
        base_url=DEFAULT_OPENAI_BASE,
        default_chat_model="gpt-4o-mini",
        default_embedding_model="text-embedding-3-small",
        requires_api_key=True,
        extra_headers={},
    ),
    "openrouter": ProviderPreset(
        transport="openai_compatible",
        base_url="https://openrouter.ai/api/v1",
        default_chat_model="openai/gpt-4o-mini",
        default_embedding_model="openai/text-embedding-3-small",
        requires_api_key=True,
        extra_headers={
            "HTTP-Referer": "https://quizarena.app",
            "X-Title": "QuizArena",
        },
    ),
       "gemini": ProviderPreset(
        transport="gemini",
        # Google AI Studio (Gemini API) — NOT Vertex AI.
        # Native REST: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
        # Auth: x-goog-api-key (AI Studio API key). Docs: https://ai.google.dev/gemini-api/docs
        base_url="https://generativelanguage.googleapis.com/v1beta",
        default_chat_model="gemini-3.6-flash",
        default_embedding_model="gemini-embedding-001",
        requires_api_key=True,
        extra_headers={},
    ),
    "anthropic": ProviderPreset(
        transport="anthropic",
        base_url="https://api.anthropic.com",
        default_chat_model="claude-3-5-haiku-latest",
        default_embedding_model="local",
        requires_api_key=True,
        extra_headers={},
        force_local_embeddings=True,
    ),
    "ollama": ProviderPreset(
        transport="openai_compatible",
        base_url="http://127.0.0.1:11434/v1",
        default_chat_model="llama3.2",
        default_embedding_model="nomic-embed-text",
        requires_api_key=False,
        extra_headers={},
        prefer_json_response_format=False,
    ),
    "openai_compatible": ProviderPreset(
        transport="openai_compatible",
        base_url=DEFAULT_OPENAI_BASE,
        default_chat_model="gpt-4o-mini",
        default_embedding_model="text-embedding-3-small",
        requires_api_key=True,
        extra_headers={},
    ),
}


@dataclass(frozen=True)
class ResolvedAiRuntime:
    """Effective provider wiring after applying presets + env overrides."""

    provider: str
    transport: Literal["openai_compatible", "anthropic", "gemini", "mock"]
    base_url: str
    chat_model: str
    embedding_model: str
    api_key: str
    requires_api_key: bool
    extra_headers: dict[str, str]
    force_local_embeddings: bool
    use_json_response_format: bool


def resolve_ai_runtime(settings: object) -> ResolvedAiRuntime:
    """Map Settings fields + named presets into concrete runtime config."""
    provider = str(getattr(settings, "ai_provider"))
    api_key = str(getattr(settings, "ai_api_key") or "").strip()
    configured_base = str(getattr(settings, "ai_api_base_url") or "").rstrip("/")
    chat_model = str(getattr(settings, "ai_chat_model") or "").strip()
    embedding_model = str(getattr(settings, "ai_embedding_model") or "").strip()

    if provider == "mock":
        return ResolvedAiRuntime(
            provider="mock",
            transport="mock",
            base_url=configured_base or DEFAULT_OPENAI_BASE,
            chat_model=chat_model or "mock",
            embedding_model=embedding_model or "mock",
            api_key=api_key,
            requires_api_key=False,
            extra_headers={},
            force_local_embeddings=True,
            use_json_response_format=True,
        )

    preset = PROVIDER_PRESETS.get(provider)
    if preset is None:
        # Unknown values are rejected by Settings Literal; defensive fallback.
        preset = PROVIDER_PRESETS["openai_compatible"]

    # Named aliases use preset base unless the operator overrode away from the
    # OpenAI default (or set an explicit base for openai_compatible).
    if provider in {"openai", "openai_compatible"}:
        base_url = configured_base or preset.base_url
    elif configured_base and configured_base != DEFAULT_OPENAI_BASE:
        base_url = configured_base
    else:
        base_url = preset.base_url

    # Prefer configured models; fall back to preset defaults when blank.
    effective_chat = chat_model or preset.default_chat_model
    effective_embed = embedding_model or preset.default_embedding_model
    if provider != "openai_compatible" and provider != "openai":
        # If still on OpenAI-centric defaults while using another vendor, swap.
        if chat_model in {"", "gpt-4o-mini"} and preset.default_chat_model != "gpt-4o-mini":
            effective_chat = preset.default_chat_model
        if embedding_model in {"", "text-embedding-3-small"} and (
            preset.default_embedding_model != "text-embedding-3-small"
            or preset.force_local_embeddings
        ):
            effective_embed = preset.default_embedding_model

    return ResolvedAiRuntime(
        provider=provider,
        transport=preset.transport,
        base_url=base_url.rstrip("/"),
        chat_model=effective_chat,
        embedding_model=effective_embed,
        api_key=api_key,
        requires_api_key=preset.requires_api_key,
        extra_headers=dict(preset.extra_headers),
        force_local_embeddings=preset.force_local_embeddings
        or effective_embed.lower() in {"local", "none", "hash", "disabled"},
        use_json_response_format=preset.prefer_json_response_format,
    )


def ai_configuration_error(settings: object) -> str | None:
    """Return a human-readable config error, or None when AI is ready."""
    app_env = str(getattr(settings, "app_env", "development"))
    if app_env == "test":
        return None

    provider = str(getattr(settings, "ai_provider", "mock"))
    runtime = resolve_ai_runtime(settings)

    if provider == "mock":
        return (
            "AI quiz generation is misconfigured: AI_PROVIDER=mock is test-only. "
            "Set AI_PROVIDER to one of: openai, openrouter, gemini, anthropic, "
            "ollama, openai_compatible — and set AI_API_KEY (except Ollama)."
        )

    if provider not in REAL_AI_PROVIDERS:
        return (
            f"AI quiz generation is misconfigured: unknown AI_PROVIDER={provider!r}. "
            "Supported: openai, openrouter, gemini, anthropic, ollama, openai_compatible."
        )

    if runtime.requires_api_key and not runtime.api_key:
        return (
            f"AI quiz generation is misconfigured: AI_API_KEY is required when "
            f"AI_PROVIDER={provider}. Set AI_API_KEY in the environment (Render secrets)."
        )

    if not runtime.base_url:
        return "AI quiz generation is misconfigured: AI_API_BASE_URL is empty."

    if not runtime.chat_model:
        return "AI quiz generation is misconfigured: AI_CHAT_MODEL is empty."

    return None
