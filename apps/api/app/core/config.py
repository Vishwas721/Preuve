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

    database_url: str = "postgresql+asyncpg://preuve:preuve@127.0.0.1:5435/preuve"
    redis_url: str = "redis://127.0.0.1:6381/0"
    searxng_url: str = "http://127.0.0.1:8888"
    # Comma-separated in env: CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_num_ctx: int = 8192  # qwen2.5 supports 32K; raise if RAM/VRAM allows
    ollama_timeout_s: float = 180.0
    gemini_api_key: str = ""
    # Fallback chain, tried in order; comma-separated in env.
    gemini_models: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash"]
    )
    gemini_timeout_s: float = 45.0
    gemini_cooldown_s: float = 300.0  # skip a model this long after a 429 / 5xx / timeout

    # Per-task provider overrides, JSON in env: LLM_ROUTE_OVERRIDES={"analyze_idea": "local"}
    llm_route_overrides: dict[str, str] = Field(default_factory=dict)
    # Let Gemini-routed tasks fall back to the local model when Gemini is unavailable.
    llm_allow_downgrade: bool = True

    # Single-user mode until Phase 5 auth: this user is created on first request.
    dev_user_email: str = "founder@preuve.local"
    dev_user_name: str = "Founder"

    @field_validator("cors_origins", "gemini_models", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
