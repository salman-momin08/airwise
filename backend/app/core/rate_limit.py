from __future__ import annotations

import time
from collections import deque

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.exceptions import RateLimitExceededError

logger = structlog.get_logger(__name__)


class SlidingWindowRateLimiter:
    """Redis-backed sliding-window rate limiter with resilient in-memory fallback."""

    def __init__(self) -> None:
        self._memory_windows: dict[str, deque[float]] = {}
        self._redis_client: Redis | None = None
        self._redis_url_cached: str | None = None
        self._redis_backoff_until: float = 0.0

    def reset_local_state(self) -> None:
        self._memory_windows.clear()
        self._redis_backoff_until = 0.0
        self._redis_client = None
        self._redis_url_cached = None

    def _get_redis(self) -> Redis | None:
        settings = get_settings()
        if (
            settings.app_env == "test"
            or not settings.redis_url
            or time.monotonic() < self._redis_backoff_until
        ):
            return None
        if self._redis_client is None or self._redis_url_cached != settings.redis_url:
            try:
                self._redis_client = Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=1.5,
                    socket_timeout=1.5,
                )
                self._redis_url_cached = settings.redis_url
            except (RedisError, ValueError) as exc:
                self._redis_client = None
                self._redis_url_cached = None
                self._redis_backoff_until = time.monotonic() + 30.0
                logger.warning(
                    "rate_limit_redis_init_fallback",
                    error_type=type(exc).__name__,
                )
                return None
        return self._redis_client

    async def check(self, scope: str, identifier: str, limit: int, window_seconds: int) -> None:
        now = time.time()
        key = f"rl:{scope}:{identifier}"
        redis = self._get_redis()
        if redis is not None:
            try:
                member = f"{now:.6f}"
                cutoff = now - window_seconds
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
            except RedisError as exc:
                self._redis_backoff_until = time.monotonic() + 30.0
                logger.warning("rate_limit_redis_fallback", scope=scope, reason=str(exc))

        bucket = self._memory_windows.setdefault(key, deque())
        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            raise RateLimitExceededError()
        bucket.append(now)


rate_limiter = SlidingWindowRateLimiter()
