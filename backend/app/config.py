"""Application configuration loaded from environment variables."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# HTTPS Vercel hosts only (production + preview). Matched with re.fullmatch.
# Does not allow bare "*", http://, or non-vercel.app domains.
DEFAULT_CORS_ORIGIN_REGEX = r"https://([a-zA-Z0-9-]+\.)*vercel\.app"

_UNSAFE_CORS_ORIGIN_REGEXES = frozenset(
    {
        "*",
        ".*",
        ".+",
        "^.*$",
        "^.+$",
        "https?://.*",
        "https://.*",
        "http://.*",
        ".*vercel.*",
        "https://*",
        "http://*",
    },
)


def _parse_string_list(value: object) -> list[str]:
    """Accept JSON arrays, CSV strings, or already-parsed lists (Render-friendly)."""
    if value is None:
        return []
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                items = [str(item).strip() for item in parsed if str(item).strip()]
            else:
                items = [item.strip() for item in stripped.split(",") if item.strip()]
        else:
            items = [item.strip() for item in stripped.split(",") if item.strip()]
    else:
        items = [str(value).strip()] if str(value).strip() else []

    normalized: list[str] = []
    for item in items:
        if item == "*":
            normalized.append(item)
        else:
            # Origins are exact-match; strip trailing slashes to avoid silent CORS failures.
            normalized.append(item.rstrip("/"))
    return normalized


def _is_absolute_http_origin(value: str) -> bool:
    """True for http(s) origins such as localhost:5173 or a Vercel URL."""
    parsed = urlparse(value)
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.netloc)
        and not parsed.username
        and not parsed.password
    )


def _is_unsafe_cors_origin_regex(pattern: str) -> bool:
    """Reject overly broad Origin regexes that would defeat allowlisting."""
    stripped = pattern.strip()
    if not stripped:
        return False
    if stripped in _UNSAFE_CORS_ORIGIN_REGEXES:
        return True
    # Patterns that match any scheme/host (still reject even with anchors).
    if stripped in {"^https?://.*$", "^https://.*$", "^http://.*$"}:
        return True
    return False


class Settings(BaseSettings):
    """QuizArena backend settings (see docs/EnvironmentVariables.md)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "production", "test"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    public_app_url: str = Field(
        default="http://localhost:5173",
        description="Public SPA origin used for join/display URLs",
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./quizarena.db",
        description="SQLAlchemy connection string (SQLite dev / PostgreSQL prod)",
    )
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=100)

    # JWT
    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_expiry_hours: int = Field(default=8, ge=1)

    # Admin seed
    admin_username: str = "admin"
    admin_password_hash: str = ""
    admin_password: str = ""

    # CORS / hosts — NoDecode so Render CSV values are not JSON-parsed first.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        description="Exact Origin allowlist (production SPA + localhost). No '*'.",
    )
    cors_origin_regex: str = Field(
        default=DEFAULT_CORS_ORIGIN_REGEX,
        description=(
            "Additional Origins matched with re.fullmatch. Default allows HTTPS "
            "*.vercel.app (production + preview). Set empty to disable."
        ),
    )
    trusted_hosts: Annotated[list[str], NoDecode] = Field(
        default=["*"],
        description="Comma-separated hosts for TrustedHostMiddleware (* disables check)",
    )

    # Uploads / request limits
    max_upload_bytes: int = Field(default=15 * 1024 * 1024, ge=1024)
    max_request_body_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)

    # File storage
    storage_backend: Literal["local", "cloud"] = "local"
    storage_path: str = "../storage"

    # AI quiz generation
    # Production / non-test: require a real provider + API key (Ollama exempt from key).
    # Supported: openai | openrouter | gemini | anthropic | ollama | openai_compatible
    # mock is APP_ENV=test only.
    ai_provider: Literal[
        "mock",
        "openai_compatible",
        "openai",
        "openrouter",
        "gemini",
        "anthropic",
        "ollama",
    ] = Field(
        default="mock",
        description=(
            "AI provider alias. Production: openai|openrouter|gemini|anthropic|"
            "ollama|openai_compatible. mock is test-only."
        ),
    )
    ai_api_key: str = Field(default="", description="API key for the configured AI provider")
    ai_api_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI-compatible API base URL (overridden by named provider presets)",
    )
    ai_chat_model: str = Field(default="gpt-4o-mini")
    ai_embedding_model: str = Field(default="text-embedding-3-small")
    ai_max_source_bytes: int = Field(default=50 * 1024 * 1024, ge=1024)
    ai_enable_topic_web: bool = Field(
        default=True,
        description="Allow trusted-web fetch for topic mode (disabled in mock)",
    )

    # Question content encryption (AES-256-GCM). Strongly recommended in production.
    question_encryption_key: str = Field(
        default="",
        description=(
            "32-byte key (urlsafe base64 or hex) or passphrase hashed to 32 bytes. "
            "When set, question prompts/explanations/options are sealed at rest."
        ),
    )

    # Rate limits (per IP, in-memory — use edge/nginx for multi-instance)
    login_rate_limit_per_minute: int = Field(default=10, ge=1)
    join_rate_limit_per_minute: int = Field(default=30, ge=1)

    @field_validator("cors_origins", "trusted_hosts", mode="before")
    @classmethod
    def parse_csv_list(cls, value: object) -> list[str]:
        return _parse_string_list(value)

    @field_validator("cors_origin_regex", mode="before")
    @classmethod
    def normalize_cors_origin_regex(cls, value: object) -> object:
        if value is None:
            return DEFAULT_CORS_ORIGIN_REGEX
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("public_app_url", mode="before")
    @classmethod
    def normalize_public_app_url(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().rstrip("/")
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        """Accept Neon/Heroku ``postgres://`` URLs and normalize for SQLAlchemy."""
        if not isinstance(value, str) or not value:
            return value
        url = value.strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        return url

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if self.app_env == "production":
            if self.jwt_secret_key in {"", "change-me-in-production", "changeme"}:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a strong secret when APP_ENV=production",
                )
            if self.debug:
                raise ValueError("DEBUG must be false when APP_ENV=production")
            if self.is_sqlite:
                raise ValueError(
                    "DATABASE_URL must use PostgreSQL when APP_ENV=production "
                    "(sqlite is development-only)",
                )
            if "*" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must not include '*' in production")
            if self.cors_origin_regex and _is_unsafe_cors_origin_regex(self.cors_origin_regex):
                raise ValueError(
                    "CORS_ORIGIN_REGEX is too broad for production "
                    "(must not match all origins; prefer HTTPS *.vercel.app)",
                )
            if self.cors_origin_regex:
                try:
                    re.compile(self.cors_origin_regex)
                except re.error as exc:
                    raise ValueError(f"CORS_ORIGIN_REGEX is not a valid regex: {exc}") from exc
            # Require an absolute http(s) SPA origin. Localhost is allowed so an
            # initial Render deploy can boot before the Vercel URL exists; a blank
            # or relative value is not. (Previously localhost was hard-rejected,
            # which made a set PUBLIC_APP_URL=http://localhost:5173 look "missing".)
            if not self.public_app_url or not _is_absolute_http_origin(self.public_app_url):
                raise ValueError(
                    "PUBLIC_APP_URL must be an absolute http(s) SPA origin "
                    "(e.g. https://app.vercel.app or http://localhost:5173) "
                    "when APP_ENV=production",
                )
            if self.trusted_hosts == ["*"] or not self.trusted_hosts:
                raise ValueError(
                    "TRUSTED_HOSTS must be set to the API hostname(s) when APP_ENV=production",
                )
            # AI must be configured before the process accepts traffic — never
            # defer AI_CONFIG_ERROR to the first generate request.
            from app.services.ai.provider_presets import ai_configuration_error

            ai_error = ai_configuration_error(self)
            if ai_error:
                raise ValueError(ai_error)
        return self

    @property
    def cors_origin_regex_or_none(self) -> str | None:
        """Regex passed to CORSMiddleware, or None when disabled."""
        return self.cors_origin_regex or None

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith(("postgresql://", "postgresql+psycopg2://"))


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance for dependency injection."""
    return Settings()
