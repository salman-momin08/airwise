from __future__ import annotations

import uuid

import pytest
from pydantic import BaseModel

from app.ai.gateway.budget import TokenBudget
from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalProviderUnavailableError, RateLimitExceededError
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security import (
    hash_ip_address,
    hash_password,
    hash_token,
    is_trusted_origin,
    verify_csrf_double_submit,
    verify_password,
)
from app.services.air_quality.cache import StaleAwareTelemetryCache
from app.services.alerts.alert_service import AlertDeduplicator


def test_argon2id_password_hashing_and_verification() -> None:
    hashed = hash_password("SmogSafe2026!")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "SmogSafe2026!") is True
    assert verify_password(hashed, "WrongPassword2026!") is False
    assert verify_password(None, "SmogSafe2026!") is False
    assert verify_password("malformed-hash", "SmogSafe2026!") is False


def test_csrf_double_submit_and_origin_validation() -> None:
    assert verify_csrf_double_submit("tok-123", "tok-123") is True
    assert verify_csrf_double_submit("tok-123", "tok-456") is False
    assert verify_csrf_double_submit(None, "tok-123") is False

    allowed = {"http://localhost:3000", "https://airwise.vercel.app"}
    assert is_trusted_origin("https://airwise.vercel.app", None, allowed) is True
    assert is_trusted_origin(None, "http://localhost:3000/dashboard/settings", allowed) is True
    assert is_trusted_origin("https://evil.example.com", None, allowed) is False


def test_hmac_token_and_ip_pseudonymization() -> None:
    secret = "unit-test-secret-key-with-sufficient-length"
    digest_a = hash_token("raw-session-token", secret)
    digest_b = hash_token("raw-session-token", secret)
    assert digest_a == digest_b
    assert digest_a != "raw-session-token"
    assert hash_ip_address("203.0.113.10", secret) is not None
    assert hash_ip_address(None, secret) is None


def test_redis_url_normalization_handles_quotes_cli_and_disabled_sentinels() -> None:
    quoted = Settings(redis_url=' "rediss://default:pw@example.upstash.io:6379" \n')
    assert quoted.redis_url == "rediss://default:pw@example.upstash.io:6379"

    cli_tls = Settings(redis_url="redis-cli --tls -u redis://default:pw@example.upstash.io:6379")
    assert cli_tls.redis_url == "rediss://default:pw@example.upstash.io:6379"

    assert Settings(redis_url="   ").redis_url == ""
    assert Settings(redis_url="none").redis_url == ""


class _DummyCachedPayload(BaseModel):
    city: str


async def test_redis_consumers_degrade_gracefully_on_invalid_url_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    misconfigured = Settings(
        app_env="development",
        redis_url="https://example-rest-endpoint.upstash.io",
    )
    monkeypatch.setattr("app.core.rate_limit.get_settings", lambda: misconfigured)
    monkeypatch.setattr("app.services.air_quality.cache.get_settings", lambda: misconfigured)

    limiter = SlidingWindowRateLimiter()
    await limiter.check("auth_register", "203.0.113.5", limit=1, window_seconds=60)
    with pytest.raises(RateLimitExceededError):
        await limiter.check("auth_register", "203.0.113.5", limit=1, window_seconds=60)

    cache = StaleAwareTelemetryCache()
    await cache.set_payload("city:delhi", _DummyCachedPayload(city="Delhi"))
    cached = await cache.get_fresh("city:delhi", _DummyCachedPayload)
    assert cached is not None and cached.city == "Delhi"

    dedup = AlertDeduplicator()
    assert await dedup.acquire(settings=misconfigured, dedup_key="a:1", ttl_seconds=60) is True
    assert await dedup.acquire(settings=misconfigured, dedup_key="a:1", ttl_seconds=60) is False

    budget = TokenBudget(misconfigured, uuid.uuid4())
    with pytest.raises(ExternalProviderUnavailableError):
        await budget.reserve(100)

    disabled_redis = Settings(app_env="development", redis_url="")
    local_budget = TokenBudget(disabled_redis, uuid.uuid4())
    await local_budget.reserve(100)
    get_settings.cache_clear()

