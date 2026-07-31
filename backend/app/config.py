"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """QuizArena backend settings (see SYSTEM_ARCHITECTURE.md §18.3)."""

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

    # Database
    database_url: str = Field(
        default="sqlite:///./quizarena.db",
        description="SQLAlchemy connection string (SQLite dev / PostgreSQL prod)",
    )

    # JWT
    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_expiry_hours: int = Field(default=8, ge=1)

    # Admin seed
    admin_username: str = "admin"
    admin_password_hash: str = ""
    admin_password: str = ""

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
    )

    # File storage
    storage_backend: Literal["local", "cloud"] = "local"
    storage_path: str = "../storage"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance for dependency injection."""
    return Settings()
