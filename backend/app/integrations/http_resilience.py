from __future__ import annotations

import asyncio
import time
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


async def fetch_json_with_resilience(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    max_attempts: int = 2,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Perform SSRF-validated HTTPS GET with explicit timeouts and bounded backoff."""
    assert_allowed_https_url(url)
    timeout = httpx.Timeout(connect=3.0, read=8.0, write=5.0, pool=3.0)
    last_exc: Exception | None = None

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        transport=transport,
    ) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.get(url, params=params, headers=headers)
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", "1.0"))
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
    raise ExternalProviderUnavailableError()
