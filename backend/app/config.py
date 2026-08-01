"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # CORS / hosts
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
    )
    trusted_hosts: list[str] = Field(
        default=["*"],
        description="Comma-separated hosts for TrustedHostMiddleware (* disables check)",
    )

    # Uploads / request limits
    max_upload_bytes: int = Field(default=15 * 1024 * 1024, ge=1024)
    max_request_body_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)

    # File storage
    storage_backend: Literal["local", "cloud"] = "local"
    storage_path: str = "../storage"

    # Rate limits (per IP, in-memory — use edge/nginx for multi-instance)
    login_rate_limit_per_minute: int = Field(default=10, ge=1)
    join_rate_limit_per_minute: int = Field(default=30, ge=1)

    @field_validator("cors_origins", "trusted_hosts", mode="before")
    @classmethod
    def parse_csv_list(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
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
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance for dependency injection."""
    return Settings()
