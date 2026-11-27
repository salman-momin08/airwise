"""SSRF-guarded outbound HTTPX client pool, retry policy, and provider circuit breaker."""

from __future__ import annotations

import asyncio
import math
import time
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from app.core.exceptions import ExternalProviderUnavailableError

logger = structlog.get_logger(__name__)

ALLOWED_EXTERNAL_ENVIRONMENTAL_HOSTS: frozenset[str] = frozenset(
    {
        "api.openaq.org",
        "api.openweathermap.org",
        "api.open-meteo.com",
        "air-quality-api.open-meteo.com",
        "api.data.gov.in",
    }
)


def assert_allowed_https_url(url: str) -> None:
    """Outbound SSRF defense: permit only allowlisted HTTPS environmental API hosts."""
    parsed = urlparse(url)
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname not in ALLOWED_EXTERNAL_ENVIRONMENTAL_HOSTS
    ):
        raise ExternalProviderUnavailableError(
            code="SSRF_HOST_BLOCKED",
            message="Outbound environmental request blocked by host allowlist.",
        )


class ProviderCircuitBreaker:
    """Lightweight per-provider circuit breaker preventing cascading upstream timeouts."""

    def __init__(
        self,
        provider_name: str,
        *,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 60.0,
    ) -> None:
        self.provider_name = provider_name
        self._failure_threshold = failure_threshold
        self._recovery_timeout_seconds = recovery_timeout_seconds
        self._failure_count = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        if (time.monotonic() - self._opened_at) >= self._recovery_timeout_seconds:
            return "half_open"
        return "open"

    def allow_request(self) -> bool:
        return self.state in {"closed", "half_open"}

    def record_success(self) -> None:
        self._failure_count = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self._opened_at = time.monotonic()
            logger.warning(
                "provider_circuit_opened",
                provider=self.provider_name,
                failures=self._failure_count,
            )

    def reset(self) -> None:
        self._failure_count = 0
        self._opened_at = None


_shared_http_client: httpx.AsyncClient | None = None
_shared_http_loop: asyncio.AbstractEventLoop | None = None
_DEFAULT_HTTP_TIMEOUT = httpx.Timeout(connect=3.0, read=8.0, write=5.0, pool=3.0)
_DEFAULT_HTTP_LIMITS = httpx.Limits(
    max_keepalive_connections=20,
    max_connections=50,
    keepalive_expiry=30.0,
)


def _get_shared_http_client() -> httpx.AsyncClient:
    global _shared_http_client, _shared_http_loop
    current_loop = asyncio.get_running_loop()
    if (
        _shared_http_client is None
        or _shared_http_client.is_closed
        or _shared_http_loop is not current_loop
    ):
        _shared_http_client = httpx.AsyncClient(
            timeout=_DEFAULT_HTTP_TIMEOUT,
            limits=_DEFAULT_HTTP_LIMITS,
            follow_redirects=False,
        )
        _shared_http_loop = current_loop
    return _shared_http_client


async def close_shared_http_clients() -> None:
    """Close shared outbound connection pool on application shutdown."""
    global _shared_http_client, _shared_http_loop
    client = _shared_http_client
    _shared_http_client = None
    _shared_http_loop = None
    if client is not None and not client.is_closed:
        await client.aclose()


def _parse_retry_after_seconds(raw_value: str | None, default: float = 1.0) -> float:
    """Parse an RFC 9110 `Retry-After` header (delta-seconds or HTTP-date) safely."""
    if not raw_value:
        return default
    cleaned = raw_value.strip()
    try:
        parsed = float(cleaned)
        if math.isfinite(parsed) and parsed >= 0.0:
            return parsed
    except ValueError:
        try:
            dt = parsedate_to_datetime(cleaned)
            delta = dt.timestamp() - time.time()
            return max(0.0, delta)
        except (TypeError, ValueError, OverflowError):
            return default
    return default


async def _execute_resilient_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None,
    headers: dict[str, str] | None,
    max_attempts: int,
) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code == 429:
                retry_after = _parse_retry_after_seconds(response.headers.get("Retry-After"))
                if attempt < max_attempts and retry_after <= 2.0:
                    await asyncio.sleep(retry_after)
                    continue
                raise ExternalProviderUnavailableError(
                    code="AIR_QUALITY_PROVIDER_RATE_LIMITED",
                    message="Upstream environmental data provider is rate-limited.",
                )
            if response.status_code >= 500 and attempt < max_attempts:
                await asyncio.sleep(0.25 * attempt)
                continue
            if 400 <= response.status_code < 500:
                logger.warning(
                    "upstream_http_client_error",
                    host=urlparse(url).hostname,
                    status_code=response.status_code,
                )
                raise ExternalProviderUnavailableError(
                    code="AIR_QUALITY_UPSTREAM_REJECTED",
                    message="Upstream environmental data provider rejected the request.",
                )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise ExternalProviderUnavailableError(
                    code="AIR_QUALITY_INVALID_UPSTREAM_PAYLOAD",
                    message="Upstream environmental data provider returned an invalid payload.",
                )
            return body
        except ExternalProviderUnavailableError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            last_exc = exc
            if attempt < max_attempts:
                await asyncio.sleep(0.25 * attempt)

    logger.warning(
        "upstream_http_exhausted",
        host=urlparse(url).hostname,
        error=type(last_exc).__name__,
    )
    raise ExternalProviderUnavailableError


async def fetch_json_with_resilience(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    max_attempts: int = 2,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Perform SSRF-validated HTTPS GET with pooled connections, timeouts, and bounded backoff."""
    assert_allowed_https_url(url)
    if transport is not None:
        async with httpx.AsyncClient(
            timeout=_DEFAULT_HTTP_TIMEOUT,
            follow_redirects=False,
            transport=transport,
        ) as isolated_client:
            return await _execute_resilient_get(
                isolated_client,
                url,
                params=params,
                headers=headers,
                max_attempts=max_attempts,
            )

    return await _execute_resilient_get(
        _get_shared_http_client(),
        url,
        params=params,
        headers=headers,
        max_attempts=max_attempts,
    )
