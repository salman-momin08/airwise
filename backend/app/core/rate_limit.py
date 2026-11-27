from __future__ import annotations

import asyncio
import time
from collections import deque

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.exceptions import RateLimitExceededError
from app.core.redis_client import create_async_redis_client

logger = structlog.get_logger(__name__)
MAX_LOCAL_RATE_WINDOWS = 2048


class SlidingWindowRateLimiter:
    """Redis-backed sliding-window rate limiter with resilient in-memory fallback."""

    def __init__(self) -> None:
        self._memory_windows: dict[str, deque[float]] = {}
        self._redis_client: Redis | None = None
        self._redis_url_cached: str | None = None
        self._redis_loop: asyncio.AbstractEventLoop | None = None
        self._redis_backoff_until: float = 0.0

    def reset_local_state(self) -> None:
        self._memory_windows.clear()
        self._redis_backoff_until = 0.0
        self._redis_client = None
        self._redis_url_cached = None
        self._redis_loop = None

    def _get_redis(self) -> Redis | None:
        settings = get_settings()
        if (
            settings.app_env == "test"
            or not settings.redis_url
            or time.monotonic() < self._redis_backoff_until
        ):
            return None
        current_loop = asyncio.get_running_loop()
        if (
            self._redis_client is None
            or self._redis_url_cached != settings.redis_url
            or self._redis_loop is not current_loop
        ):
            try:
                self._redis_client = create_async_redis_client(
                    settings.redis_url,
                    decode_responses=True,
                )
                self._redis_url_cached = settings.redis_url
                self._redis_loop = current_loop
            except (RedisError, ValueError) as exc:
                self._redis_client = None
                self._redis_url_cached = None
                self._redis_loop = None
                self._redis_backoff_until = time.monotonic() + 30.0
                logger.warning(
                    "rate_limit_redis_init_fallback",
                    error_type=type(exc).__name__,
                )
                return None
        return self._redis_client

    async def check(self, scope: str, identifier: str, limit: int, window_seconds: int) -> None:
        now = time.time()
        cutoff = now - window_seconds
        key = f"rl:{scope}:{identifier}"
        redis = self._get_redis()
        if redis is not None:
            try:
                member = f"{now:.6f}"
                pipe = redis.pipeline()
                pipe.zremrangebyscore(key, "-inf", cutoff)
                pipe.zcard(key)
                pipe.zadd(key, {member: now})
                pipe.expire(key, window_seconds + 5)
                results = await pipe.execute()
                current_count = int(results[1])
                if current_count >= limit:
                    raise RateLimitExceededError()
                return
            except RateLimitExceededError:
                raise
            except (RedisError, RuntimeError) as exc:
                self._redis_client = None
                self._redis_loop = None
                self._redis_backoff_until = time.monotonic() + 30.0
                logger.warning("rate_limit_redis_fallback", scope=scope, reason=str(exc))

        if key not in self._memory_windows and len(self._memory_windows) >= MAX_LOCAL_RATE_WINDOWS:
            empty_keys = [
                k for k, q in self._memory_windows.items() if not q or q[-1] <= cutoff
            ]
            for k in empty_keys:
                self._memory_windows.pop(k, None)
            if len(self._memory_windows) >= MAX_LOCAL_RATE_WINDOWS:
                oldest_key = next(iter(self._memory_windows))
                self._memory_windows.pop(oldest_key, None)
        bucket = self._memory_windows.setdefault(key, deque())
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            raise RateLimitExceededError()
        bucket.append(now)


rate_limiter = SlidingWindowRateLimiter()
