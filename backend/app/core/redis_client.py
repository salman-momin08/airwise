"""Async Redis client factory with serverless TLS normalization and timeout defaults."""

from __future__ import annotations

from redis.asyncio import Redis
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from redis.retry import Retry


def create_async_redis_client(url: str, *, decode_responses: bool = True) -> Redis:
    """Create a serverless-resilient async Redis client with idle health checks and retry."""
    client: Redis = Redis.from_url(
        url,
        decode_responses=decode_responses,
        socket_connect_timeout=2.5,
        socket_timeout=2.5,
        socket_keepalive=True,
        health_check_interval=15,
        retry=Retry(ExponentialBackoff(cap=0.5, base=0.1), 1),
        retry_on_error=[RedisConnectionError, RedisTimeoutError],
    )
    return client
