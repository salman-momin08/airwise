"""Per-user daily AI token budget enforcement backed by atomic Redis Lua scripts."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import ClassVar, cast
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError, RateLimitExceededError
from app.core.redis_client import create_async_redis_client

logger = structlog.get_logger(__name__)
MAX_LOCAL_BUDGET_KEYS = 1024
_RESERVE = """
local used = tonumber(redis.call('GET', KEYS[1]) or '0')
local amount = tonumber(ARGV[1])
if used + amount > tonumber(ARGV[2]) then return 0 end
redis.call('INCRBY', KEYS[1], amount)
redis.call('EXPIRE', KEYS[1], 172800)
return 1
"""


class TokenBudget:
    """Enforce daily per-user LLM token caps across serverless or worker processes."""

    _test_usage: ClassVar[dict[str, int]] = {}
    _redis_client: ClassVar[Redis | None] = None
    _redis_url_cached: ClassVar[str | None] = None
    _redis_loop: ClassVar[asyncio.AbstractEventLoop | None] = None

    def __init__(self, settings: Settings, user_id: UUID) -> None:
        self._settings = settings
        self._today = f"{datetime.now(UTC):%Y-%m-%d}"
        self._key = f"ai:tokens:{self._today}:{user_id}"

    @classmethod
    def reset_local_state(cls) -> None:
        """Reset in-memory test counters and cached Redis client state."""
        cls._test_usage.clear()
        cls._redis_client = None
        cls._redis_url_cached = None
        cls._redis_loop = None

    @classmethod
    def _invalidate_redis_client(cls) -> None:
        cls._redis_client = None
        cls._redis_loop = None

    @classmethod
    async def aclose(cls) -> None:
        """Close the shared Redis client connection pool on application shutdown."""
        client = cls._redis_client
        cls._redis_client = None
        cls._redis_url_cached = None
        cls._redis_loop = None
        if client is not None:
            await client.aclose()

    @classmethod
    def _get_redis(cls, redis_url: str) -> Redis:
        current_loop = asyncio.get_running_loop()
        if (
            cls._redis_client is None
            or cls._redis_url_cached != redis_url
            or cls._redis_loop is not current_loop
        ):
            cls._redis_client = create_async_redis_client(
                redis_url,
                decode_responses=False,
            )
            cls._redis_url_cached = redis_url
            cls._redis_loop = current_loop
        return cls._redis_client

    async def reserve(self, tokens: int) -> None:
        if self._settings.app_env == "test" or not self._settings.redis_url:
            if len(self._test_usage) >= MAX_LOCAL_BUDGET_KEYS:
                today_prefix = f"ai:tokens:{self._today}:"
                stale_keys = [k for k in self._test_usage if not k.startswith(today_prefix)]
                for k in stale_keys:
                    self._test_usage.pop(k, None)
                if len(self._test_usage) >= MAX_LOCAL_BUDGET_KEYS:
                    oldest_key = next(iter(self._test_usage))
                    self._test_usage.pop(oldest_key, None)
            used = self._test_usage.get(self._key, 0)
            if used + tokens > self._settings.ai_daily_token_budget:
                raise RateLimitExceededError(code="AI_DAILY_BUDGET_EXCEEDED")
            self._test_usage[self._key] = used + tokens
            return
        try:
            redis = self._get_redis(self._settings.redis_url)
            allowed = await cast(
                Awaitable[int],
                redis.eval(
                    _RESERVE,
                    1,
                    self._key,
                    str(tokens),
                    str(self._settings.ai_daily_token_budget),
                ),
            )
            if not allowed:
                raise RateLimitExceededError(code="AI_DAILY_BUDGET_EXCEEDED")
        except (RedisError, ValueError, RuntimeError) as exc:
            self._invalidate_redis_client()
            logger.warning("ai_token_budget_unavailable", error_type=type(exc).__name__)
            raise ExternalProviderUnavailableError(
                code="AI_BUDGET_UNAVAILABLE",
                message="AI usage limits cannot be checked right now. Please try again.",
            ) from None
