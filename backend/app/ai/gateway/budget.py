from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError, RateLimitExceededError

logger = structlog.get_logger(__name__)
_RESERVE = """
local used = tonumber(redis.call('GET', KEYS[1]) or '0')
local amount = tonumber(ARGV[1])
if used + amount > tonumber(ARGV[2]) then return 0 end
redis.call('INCRBY', KEYS[1], amount)
redis.call('EXPIRE', KEYS[1], 172800)
return 1
"""


class TokenBudget:
    _test_usage: dict[str, int] = {}

    def __init__(self, settings: Settings, user_id: UUID) -> None:
        self._settings = settings
        self._key = f"ai:tokens:{datetime.now(UTC):%Y-%m-%d}:{user_id}"

    async def reserve(self, tokens: int) -> None:
        if self._settings.app_env == "test" or not self._settings.redis_url:
            used = self._test_usage.get(self._key, 0)
            if used + tokens > self._settings.ai_daily_token_budget:
                raise RateLimitExceededError(code="AI_DAILY_BUDGET_EXCEEDED")
            self._test_usage[self._key] = used + tokens
            return
        try:
            async with Redis.from_url(
                self._settings.redis_url, socket_connect_timeout=1.5, socket_timeout=1.5
            ) as redis:
                allowed = await redis.eval(
                    _RESERVE, 1, self._key, tokens, self._settings.ai_daily_token_budget
                )
                if not allowed:
                    raise RateLimitExceededError(code="AI_DAILY_BUDGET_EXCEEDED")
        except (RedisError, ValueError) as exc:
            logger.warning("ai_token_budget_unavailable", error_type=type(exc).__name__)
            raise ExternalProviderUnavailableError(
                code="AI_BUDGET_UNAVAILABLE",
                message="AI usage limits cannot be checked right now. Please try again.",
            ) from None
