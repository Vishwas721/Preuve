from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Repo root `.env` (apps/api/app/core/config.py -> ../../../../.env), then a local one.
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Preuve API"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://preuve:preuve@127.0.0.1:5433/preuve"
    redis_url: str = "redis://127.0.0.1:6379/0"
    searxng_url: str = "http://127.0.0.1:8888"
    # Comma-separated in env: CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3:8b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Single-user mode until Phase 5 auth: this user is created on first request.
    dev_user_email: str = "founder@preuve.local"
    dev_user_name: str = "Founder"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
