"""Structured JSON/console logging configuration with recursive secret and PII redaction."""

from __future__ import annotations

import logging
from typing import Any

REDACTED_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "authorization",
        "cookie",
        "set-cookie",
        "x-csrf-token",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "api_key",
        "openai_api_key",
        "gemini_api_key",
        "email_api_key",
        "air_quality_api_key",
        "air_quality_fallback_api_key",
        "weather_api_key",
        "geocoding_api_key",
        "google_oauth_client_secret",
        "database_url",
        "redis_url",
        "cron_secret",
        "metrics_internal_token",
        "auth_secret_key",
    }
)


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return redact_sensitive_mapping(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def redact_sensitive_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    """Redact credentials, cookies, and secret keys prior to logging."""
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in REDACTED_KEYS:
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = _redact_value(value)
    return sanitized


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    # Prevent httpx/httpcore from logging outbound request URLs containing query-string secrets
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
