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
        "api_key",
        "openai_api_key",
        "auth_secret_key",
    }
)


def redact_sensitive_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    """Redact credentials, cookies, and secret keys prior to logging."""
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key.lower() in REDACTED_KEYS:
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = redact_sensitive_mapping(value)
        else:
            sanitized[key] = value
    return sanitized


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
