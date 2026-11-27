from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TypeVar

import structlog
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.redis_client import create_async_redis_client
from app.core.telemetry import telemetry_registry

logger = structlog.get_logger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

DEFAULT_FRESH_TTL_SECONDS = 900
DEFAULT_STALE_BACKUP_TTL_SECONDS = 12 * 3600
MAX_LOCAL_CACHE_ENTRIES = 512


@dataclass
class _MemoryCacheItem:
    raw_json: str
    fresh_until: float
    stale_until: float


class StaleAwareTelemetryCache:
    """Redis-backed telemetry cache with explicit stale-backup retention.

    Never serves an expired cache entry as fresh: once `fresh_until` passes,
    `get_stale_backup` returns the payload only so callers can explicitly set `is_stale=True`.
    """

    def __init__(self) -> None:
        self._memory: dict[str, _MemoryCacheItem] = {}
        self._redis_client: Redis | None = None
        self._redis_url_cached: str | None = None
        self._redis_loop: asyncio.AbstractEventLoop | None = None
        self._redis_backoff_until: float = 0.0

    def clear_local(self) -> None:
        self._memory.clear()
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
                    "telemetry_cache_redis_init_fallback",
                    error_type=type(exc).__name__,
                )
                return None
        return self._redis_client

    async def get_fresh(self, key: str, model_cls: type[ModelT]) -> ModelT | None:
        redis = self._get_redis()
        if redis is not None:
            try:
                raw = await redis.get(f"fresh:{key}")
                if raw is not None:
                    telemetry_registry.aqi_cache_hits_total += 1
                    return model_cls.model_validate_json(raw)
                telemetry_registry.aqi_cache_misses_total += 1
                return None
            except (RedisError, RuntimeError) as exc:
                self._redis_client = None
                self._redis_loop = None
                self._redis_backoff_until = time.monotonic() + 30.0
                logger.warning("telemetry_cache_read_fallback", key=key, reason=str(exc))

        entry = self._memory.get(key)
        if entry is None:
            telemetry_registry.aqi_cache_misses_total += 1
            return None
        if time.monotonic() <= entry.fresh_until:
            telemetry_registry.aqi_cache_hits_total += 1
            return model_cls.model_validate_json(entry.raw_json)
        telemetry_registry.aqi_cache_misses_total += 1
        return None

    async def get_stale_backup(self, key: str, model_cls: type[ModelT]) -> ModelT | None:
        redis = self._get_redis()
        if redis is not None:
            try:
                raw = await redis.get(f"stale:{key}")
                if raw is not None:
                    return model_cls.model_validate_json(raw)
                return None
            except (RedisError, RuntimeError) as exc:
                self._redis_client = None
                self._redis_loop = None
                self._redis_backoff_until = time.monotonic() + 30.0
                logger.warning("telemetry_stale_read_fallback", key=key, reason=str(exc))

        entry = self._memory.get(key)
        if entry is None:
            return None
        if time.monotonic() <= entry.stale_until:
            return model_cls.model_validate_json(entry.raw_json)
        self._memory.pop(key, None)
        return None

    async def set_payload(
        self,
        key: str,
        payload: BaseModel,
        *,
        fresh_ttl_seconds: int = DEFAULT_FRESH_TTL_SECONDS,
        stale_ttl_seconds: int = DEFAULT_STALE_BACKUP_TTL_SECONDS,
    ) -> None:
        raw_json = payload.model_dump_json()
        now = time.monotonic()
        if key not in self._memory and len(self._memory) >= MAX_LOCAL_CACHE_ENTRIES:
            expired_keys = [k for k, item in self._memory.items() if item.stale_until <= now]
            for k in expired_keys:
                self._memory.pop(k, None)
            if len(self._memory) >= MAX_LOCAL_CACHE_ENTRIES:
                oldest_key = min(self._memory, key=lambda k: self._memory[k].stale_until)
                self._memory.pop(oldest_key, None)
        self._memory[key] = _MemoryCacheItem(
            raw_json=raw_json,
            fresh_until=now + fresh_ttl_seconds,
            stale_until=now + stale_ttl_seconds,
        )
        redis = self._get_redis()
        if redis is not None:
            try:
                pipe = redis.pipeline()
                pipe.setex(f"fresh:{key}", fresh_ttl_seconds, raw_json)
                pipe.setex(f"stale:{key}", stale_ttl_seconds, raw_json)
                await pipe.execute()
            except (RedisError, RuntimeError) as exc:
                self._redis_client = None
                self._redis_loop = None
                self._redis_backoff_until = time.monotonic() + 30.0
                logger.warning("telemetry_cache_write_fallback", key=key, reason=str(exc))

    def expire_fresh_for_testing(self, key: str) -> None:
        """Expire only the fresh window so tests can verify stale-backup warning behavior."""
        entry = self._memory.get(key)
        if entry is not None:
            entry.fresh_until = time.monotonic() - 1.0


telemetry_cache = StaleAwareTelemetryCache()
