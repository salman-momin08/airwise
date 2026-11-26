from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AirWise AI"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://airwise:airwise_dev_only@localhost:5432/airwise"
    redis_url: str = "redis://localhost:6379/0"

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

    air_quality_provider: Literal["openaq", "openweather", "cpcb", "fixture"] = "fixture"
    air_quality_fallback_provider: Literal["openaq", "openweather", "none"] = "openweather"
    air_quality_api_key: str = ""

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
