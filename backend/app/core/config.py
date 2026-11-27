from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT_DIR = _BACKEND_DIR.parent

VALID_REDIS_SCHEMES = ("redis://", "rediss://", "unix://")
_DISABLED_REDIS_SENTINELS = frozenset({"", "none", "null", "false", "disabled"})


def _strip_wrapping_quotes(value: str) -> str:
    trimmed = value.strip()
    if len(trimmed) >= 2 and trimmed[0] == trimmed[-1] and trimmed[0] in {'"', "'"}:
        return trimmed[1:-1].strip()
    return trimmed


def _upgrade_managed_tls_scheme(url: str) -> str:
    """Upstash endpoints require TLS (`rediss://`); plain `redis://` drops immediately."""
    if not url.startswith("redis://"):
        return url
    hostname = (urlsplit(url).hostname or "").lower()
    if hostname.endswith(".upstash.io"):
        return "rediss://" + url.removeprefix("redis://")
    return url


def normalize_redis_url(raw: str) -> str:
    """Normalize common Vercel/Upstash paste variants (quotes, whitespace, redis-cli, TLS)."""
    cleaned = _strip_wrapping_quotes(raw)
    if cleaned.lower() in _DISABLED_REDIS_SENTINELS:
        return ""
    if cleaned.startswith("redis-cli"):
        tokens = cleaned.split()
        use_tls = "--tls" in tokens
        extracted = ""
        for idx, tok in enumerate(tokens):
            stripped_tok = _strip_wrapping_quotes(tok)
            if stripped_tok in {"-u", "--uri"} and idx + 1 < len(tokens):
                extracted = _strip_wrapping_quotes(tokens[idx + 1])
                break
            if stripped_tok.startswith(VALID_REDIS_SCHEMES):
                extracted = stripped_tok
                break
        if extracted:
            if use_tls and extracted.startswith("redis://"):
                return "rediss://" + extracted.removeprefix("redis://")
            return _upgrade_managed_tls_scheme(extracted)
    return _upgrade_managed_tls_scheme(cleaned)


def is_valid_redis_url(url: str) -> bool:
    return bool(url) and url.startswith(VALID_REDIS_SCHEMES)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT_DIR / ".env", _BACKEND_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **values: Any) -> None:
        if "_env_file" not in values and (
            values.get("app_env") == "test" or os.getenv("APP_ENV") == "test"
        ):
            values["_env_file"] = None
        super().__init__(**values)

    app_name: str = "AirWise AI"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://airwise:airwise_dev_only@localhost:5432/airwise"
    redis_url: str = "redis://localhost:6379/0"

    @field_validator("redis_url", mode="before")
    @classmethod
    def _clean_redis_url(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_redis_url(value)
        return value

    auth_secret_key: str = Field(
        default="dev-only-replace-with-cryptographic-random-secret-key",
        min_length=32,
    )
    auth_cookie_secure: bool = False
    auth_session_ttl_seconds: int = 86400

    llm_provider: Literal["gemini"] = "gemini"
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = Field(default="gemini-2.5-flash", pattern=r"^[a-zA-Z0-9._-]+$")
    embedding_model: str = Field(default="gemini-embedding-001", pattern=r"^[a-zA-Z0-9._-]+$")
    ai_max_output_tokens: int = Field(default=2048, ge=256, le=4096)
    ai_daily_token_budget: int = Field(default=200000, ge=1000)
    ai_requests_per_minute: int = Field(default=10, ge=1, le=60)

    air_quality_provider: Literal["openaq", "openweather", "open_meteo", "cpcb", "fixture"] = (
        "fixture"
    )
    air_quality_fallback_provider: Literal["openaq", "openweather", "open_meteo", "none"] = (
        "open_meteo"
    )
    air_quality_api_key: str = Field(default="", repr=False)
    air_quality_fallback_api_key: str = Field(default="", repr=False)

    weather_provider: Literal["openweather", "open_meteo", "fixture"] = "fixture"
    weather_api_key: str = ""

    geocoding_provider: Literal["openweather", "mapbox"] = "openweather"
    geocoding_api_key: str = ""

    email_provider: Literal["console", "resend"] = "console"
    email_api_key: str = ""
    email_from_address: str = "no-reply@airwise.app"

    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/auth/oauth/google/callback"

    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    database_serverless_pool: bool = False
    cron_secret: str = ""

    otel_service_name: str = "airwise-backend"
    metrics_internal_token: str = ""

    @model_validator(mode="after")
    def validate_production_invariants(self) -> Settings:
        if self.app_env == "production":
            if self.debug:
                raise ValueError("DEBUG must be false when APP_ENV=production.")
            if not self.auth_cookie_secure:
                raise ValueError("AUTH_COOKIE_SECURE must be true when APP_ENV=production.")
            if self.air_quality_provider == "fixture" or self.weather_provider == "fixture":
                raise ValueError(
                    "Development 'fixture' providers are strictly prohibited "
                    "when APP_ENV=production."
                )
            if self.auth_secret_key.startswith("dev-only"):
                raise ValueError("Production AUTH_SECRET_KEY must not use the dev placeholder.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
