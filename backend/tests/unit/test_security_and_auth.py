from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from pydantic import BaseModel

from app.ai.gateway.budget import TokenBudget
from app.core.config import Settings, get_settings
from app.core.exceptions import ExternalProviderUnavailableError, RateLimitExceededError
from app.core.logging import redact_sensitive_mapping
from app.core.rate_limit import MAX_LOCAL_RATE_WINDOWS, SlidingWindowRateLimiter
from app.core.security import (
    hash_ip_address,
    hash_password,
    hash_token,
    is_trusted_origin,
    verify_csrf_double_submit,
    verify_password,
)
from app.integrations.http_resilience import _parse_retry_after_seconds
from app.main import create_app
from app.services.air_quality.cache import MAX_LOCAL_CACHE_ENTRIES, StaleAwareTelemetryCache
from app.services.alerts.alert_service import AlertDeduplicator
from app.services.auth.oauth import GoogleOAuthAdapterStub
from app.workers.alert_tasks import evaluate_active_alert_rules
from app.workers.ingestion_tasks import poll_air_quality_sources
from app.workers.maintenance_tasks import cleanup_expired_sessions


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

    plain_upstash = Settings(redis_url="redis://default:pw@example.upstash.io:6379")
    assert plain_upstash.redis_url == "rediss://default:pw@example.upstash.io:6379"

    local_redis = Settings(redis_url="redis://localhost:6379/0")
    assert local_redis.redis_url == "redis://localhost:6379/0"

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
    assert cached is not None
    assert cached.city == "Delhi"

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


async def test_settings_secret_repr_redaction_and_bounded_local_memory() -> None:
    cfg = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://user:super-secret-db-pass@db.internal:5432/airwise",
        redis_url="rediss://default:super-secret-redis-pass@cache.upstash.io:6379",
        auth_secret_key="super-secret-auth-signing-key-at-least-32-bytes",
        gemini_api_key="super-secret-gemini-key",
        air_quality_api_key="super-secret-openaq-key",
        air_quality_fallback_api_key="super-secret-fallback-key",
        weather_api_key="super-secret-weather-key",
        email_api_key="super-secret-resend-key",
        google_oauth_client_secret="super-secret-google-oauth",
        cron_secret="super-secret-cron-token",
        metrics_internal_token="super-secret-metrics-token",
    )
    rendered = repr(cfg)
    for secret_fragment in (
        "super-secret-db-pass",
        "super-secret-redis-pass",
        "super-secret-auth-signing-key",
        "super-secret-gemini-key",
        "super-secret-openaq-key",
        "super-secret-fallback-key",
        "super-secret-weather-key",
        "super-secret-resend-key",
        "super-secret-google-oauth",
        "super-secret-cron-token",
        "super-secret-metrics-token",
    ):
        assert secret_fragment not in rendered

    redacted = redact_sensitive_mapping(
        {
            "city": "Delhi",
            "google_oauth_client_secret": "raw-oauth-secret",
            "nested": [{"refresh_token": "raw-refresh", "safe": "ok"}],
        }
    )
    assert redacted["city"] == "Delhi"
    assert redacted["google_oauth_client_secret"] == "[REDACTED]"
    assert redacted["nested"][0]["refresh_token"] == "[REDACTED]"
    assert redacted["nested"][0]["safe"] == "ok"

    cache = StaleAwareTelemetryCache()
    for idx in range(MAX_LOCAL_CACHE_ENTRIES + 25):
        await cache.set_payload(f"city:{idx}", _DummyCachedPayload(city=f"City-{idx}"))
    assert cache.local_entry_count <= MAX_LOCAL_CACHE_ENTRIES

    limiter = SlidingWindowRateLimiter()
    for idx in range(MAX_LOCAL_RATE_WINDOWS + 25):
        await limiter.check("public_aqi", f"198.51.100.{idx}", limit=5, window_seconds=60)
    assert limiter.local_window_count <= MAX_LOCAL_RATE_WINDOWS


def test_no_multiple_consecutive_blank_lines_across_codebase() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    skip_dirs = {
        ".git",
        ".venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
        ".next",
        "airwise_backend.egg-info",
        "__pycache__",
        "playwright-report",
        "test-results",
    }
    non_python_multi_blank = re.compile(r"(?:\r?\n[ \t]*){3,}")
    python_excess_blank = re.compile(r"(?:\r?\n[ \t]*){4,}")
    offenders: list[str] = []
    for path in repo_root.rglob("*"):
        if any(part in skip_dirs for part in path.parts) or not path.is_file():
            continue
        raw = path.read_bytes()
        if not raw:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        pattern = python_excess_blank if path.suffix == ".py" else non_python_multi_blank
        if pattern.search(text):
            offenders.append(path.relative_to(repo_root).as_posix())
    assert offenders == []


def test_production_invariants_oauth_encoding_and_retry_after_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allowed = {"https://airwise.app"}
    assert is_trusted_origin("null", None, allowed) is False
    assert is_trusted_origin(None, "javascript:alert(1)", allowed) is False
    assert is_trusted_origin("https://airwise.app", None, allowed) is True

    # Production config rejects dev DB credentials and missing metrics token
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(
            app_env="production",
            debug=False,
            auth_cookie_secure=True,
            air_quality_provider="open_meteo",
            weather_provider="open_meteo",
            auth_secret_key="prod-cryptographic-random-secret-key-32b",
            database_url="postgresql+asyncpg://airwise:airwise_dev_only@db:5432/airwise",
            metrics_internal_token="prod-metrics-token",
        )

    with pytest.raises(ValueError, match="METRICS_INTERNAL_TOKEN"):
        Settings(
            app_env="production",
            debug=False,
            auth_cookie_secure=True,
            air_quality_provider="open_meteo",
            weather_provider="open_meteo",
            auth_secret_key="prod-cryptographic-random-secret-key-32b",
            database_url="postgresql+asyncpg://airwise:prod-strong-db-pass@db:5432/airwise",
            metrics_internal_token="",
        )

    prod_cfg = Settings(
        app_env="production",
        debug=False,
        auth_cookie_secure=True,
        air_quality_provider="open_meteo",
        weather_provider="open_meteo",
        auth_secret_key="prod-cryptographic-random-secret-key-32b",
        database_url="postgresql+asyncpg://airwise:prod-strong-db-pass@db:5432/airwise",
        metrics_internal_token="prod-metrics-token",
        google_oauth_client_id="cid-123",
        google_oauth_client_secret="csec-456",
        google_oauth_redirect_uri="https://airwise.app/api/v1/auth/oauth/google/callback",
    )
    monkeypatch.setattr("app.main.get_settings", lambda: prod_cfg)
    prod_app = create_app()
    assert prod_app.openapi_url is None
    assert prod_app.docs_url is None
    assert prod_app.redoc_url is None

    oauth = GoogleOAuthAdapterStub(prod_cfg)
    auth_url = oauth.build_authorization_url("state+token/1")
    assert (
        "redirect_uri=https%3A%2F%2Fairwise.app%2Fapi%2Fv1%2Fauth%2Foauth%2Fgoogle%2Fcallback"
        in auth_url
    )
    assert "state=state%2Btoken%2F1" in auth_url

    assert _parse_retry_after_seconds("1.5") == 1.5
    assert _parse_retry_after_seconds("NaN") == 1.0
    assert _parse_retry_after_seconds("-4") == 1.0
    assert _parse_retry_after_seconds("not-a-date") == 1.0
    assert _parse_retry_after_seconds("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0


def test_celery_worker_entrypoints_execute_idempotently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_alert_eval() -> dict[str, object]:
        return {"evaluated_rules": 2, "triggered_notifications": 1}

    async def _fake_ingestion() -> dict[str, int]:
        return {"ingested_cities": 4, "failed_cities": 0}

    async def _fake_cleanup() -> int:
        return 3

    monkeypatch.setattr("app.workers.alert_tasks._run_alert_evaluation", _fake_alert_eval)
    monkeypatch.setattr("app.workers.ingestion_tasks._run_priority_ingestion", _fake_ingestion)
    monkeypatch.setattr("app.workers.maintenance_tasks._run_session_cleanup", _fake_cleanup)

    alert_res = evaluate_active_alert_rules()
    assert alert_res["status"] == "completed"
    assert alert_res["evaluated_rules"] == 2

    ing_res = poll_air_quality_sources()
    assert ing_res["status"] == "completed"
    assert ing_res["ingested_cities"] == 4

    maint_res = cleanup_expired_sessions()
    assert maint_res == {"status": "completed", "purged_expired_sessions": 3}
