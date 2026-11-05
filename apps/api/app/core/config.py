from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Repo root `.env` (apps/api/app/core/config.py -> ../../../../.env), then a local one.
DEV_OUTREACH_SECRET = "dev-outreach-secret-change-me"
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

    # Outreach email (Phase 2). Empty smtp_host disables sending.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False
    smtp_ssl: bool = False
    smtp_timeout_s: float = 30.0
    email_from_name: str = ""
    email_from_address: str = ""
    email_postal_address: str = ""
    outreach_secret: str = DEV_OUTREACH_SECRET
    public_api_url: str = "http://localhost:8000"
    outreach_daily_limit: int = 20  # across all campaigns
    outreach_cooldown_days: int = 30  # min days between two emails to one address

    # Reply ingestion (Phase 3). Empty imap_host disables polling.
    imap_host: str = ""
    imap_port: int = 993
    imap_ssl: bool = True
    imap_username: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    imap_poll_minutes: int = 5
    imap_timeout_s: float = 30.0
    # Private text (replies, interview notes) may only escalate to Gemini when this is true.
    allow_private_to_gemini: bool = False

    # Single-user mode until Phase 5 auth: this user is created on first request.
    # Phase 5A auth. Open sign-up is off: people join a workspace through an invitation.
    allow_signup: bool = False
    # The pre-5A single user; first-run setup claims it (and the data it owns).
    dev_user_email: str = "founder@preuve.local"
    dev_user_name: str = "Founder"

    # Behind a reverse proxy / Cloudflare Tunnel (5D): take the client IP from its headers.
    trust_proxy_headers: bool = False
    # Phase 5D: `json` in production (one object per line, with request ids).
    log_format: str = "text"
    log_level: str = "INFO"
    # Optional error reporting; empty = off, nothing leaves the machine.
    sentry_dsn: str = ""
    max_request_bytes: int = 5_000_000

    @model_validator(mode="after")
    def _no_dev_secrets_in_production(self) -> "Settings":
        """Phase 5C: refuse to start outside development with the dev outreach secret (it
        signs unsubscribe links) or a short one."""
        weak = self.outreach_secret == DEV_OUTREACH_SECRET or len(self.outreach_secret) < 32
        if self.environment != "development" and weak:
            raise ValueError(
                "OUTREACH_SECRET must be a random value of 32+ characters outside development, "
                "e.g. the output of: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        return self

    @field_validator("cors_origins", "gemini_models", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
