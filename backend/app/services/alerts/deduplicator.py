"""Alert deduplication, timezone-aware quiet-hours checks, and alert/notification serializers."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time
from typing import cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.redis_client import create_async_redis_client
from app.models.community_alerts import AlertRule, Notification
from app.schemas.alerts import (
    AlertChannelLiteral,
    AlertRuleSchema,
    AlertTypeLiteral,
    DeliveryStatusLiteral,
    NotificationDeliverySchema,
    NotificationSchema,
    NotificationSeverityLiteral,
)
from app.services.air_quality.aqi_calculator import AQIStandard

logger = structlog.get_logger(__name__)

MAX_LOCAL_DEDUP_KEYS = 2048


def parse_hhmm_optional(value: str | None) -> time | None:
    """Parse an optional `HH:MM` clock string into a `datetime.time` object."""
    if value is None:
        return None
    parts = value.split(":")
    return time(hour=int(parts[0]), minute=int(parts[1]))


def ensure_utc(value: datetime) -> datetime:
    """Normalize naive or offset-aware datetimes to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_within_quiet_hours(
    *,
    utc_now: datetime,
    timezone_name: str,
    quiet_start: time | None,
    quiet_end: time | None,
) -> bool:
    """Evaluate timezone-aware quiet hours, including overnight spans (e.g. 22:00 -> 07:00)."""
    if quiet_start is None or quiet_end is None or quiet_start == quiet_end:
        return False
    try:
        tz = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, KeyError):
        tz = ZoneInfo("UTC")

    local_dt = ensure_utc(utc_now).astimezone(tz)
    local_clock = time(hour=local_dt.hour, minute=local_dt.minute)
    if quiet_start < quiet_end:
        return quiet_start <= local_clock < quiet_end
    return local_clock >= quiet_start or local_clock < quiet_end


class AlertDeduplicator:
    """Redis SET-NX deduplicator with resilient in-memory fallback for tests/local dev."""

    def __init__(self) -> None:
        self._local_keys: dict[str, float] = {}
        self._redis_client: Redis | None = None
        self._redis_url_cached: str | None = None
        self._redis_loop: asyncio.AbstractEventLoop | None = None

    def reset_local_state(self) -> None:
        """Clear local deduplication state and cached Redis references."""
        self._local_keys.clear()
        self._redis_client = None
        self._redis_url_cached = None
        self._redis_loop = None

    async def aclose(self) -> None:
        """Close the shared Redis client connection pool on application shutdown."""
        client = self._redis_client
        self._redis_client = None
        self._redis_url_cached = None
        self._redis_loop = None
        if client is not None:
            await client.aclose()

    def _get_redis(self, redis_url: str) -> Redis:
        current_loop = asyncio.get_running_loop()
        if (
            self._redis_client is None
            or self._redis_url_cached != redis_url
            or self._redis_loop is not current_loop
        ):
            self._redis_client = create_async_redis_client(
                redis_url,
                decode_responses=True,
            )
            self._redis_url_cached = redis_url
            self._redis_loop = current_loop
        return self._redis_client

    async def acquire(self, *, settings: Settings, dedup_key: str, ttl_seconds: int) -> bool:
        """Acquire a cooldown lock for `dedup_key`; return False when already active."""
        now_ts = datetime.now(tz=UTC).timestamp()
        expired = [k for k, exp in self._local_keys.items() if exp <= now_ts]
        for k in expired:
            self._local_keys.pop(k, None)

        if settings.app_env != "test" and settings.redis_url:
            try:
                redis = self._get_redis(settings.redis_url)
                acquired = await redis.set(dedup_key, "1", ex=max(ttl_seconds, 60), nx=True)
                return bool(acquired)
            except (RedisError, ValueError, RuntimeError) as exc:
                self._redis_client = None
                self._redis_loop = None
                logger.warning("alert_dedup_redis_fallback", error_type=type(exc).__name__)

        if dedup_key in self._local_keys:
            return False
        if len(self._local_keys) >= MAX_LOCAL_DEDUP_KEYS:
            oldest_key = min(self._local_keys, key=lambda k: self._local_keys[k])
            self._local_keys.pop(oldest_key, None)
        self._local_keys[dedup_key] = now_ts + max(ttl_seconds, 60)
        return True


alert_deduplicator = AlertDeduplicator()


def serialize_alert_rule(rule: AlertRule) -> AlertRuleSchema:
    """Convert an `AlertRule` ORM entity into its API response DTO."""
    std = (
        AQIStandard.US_EPA
        if rule.aqi_standard == AQIStandard.US_EPA.value
        else AQIStandard.INDIA_NAQI
    )
    return AlertRuleSchema(
        id=rule.id,
        location_id=rule.location_id,
        city=rule.city,
        alert_type=cast(AlertTypeLiteral, rule.alert_type),
        aqi_standard=std,
        threshold_value=rule.threshold_value,
        channels=[cast(AlertChannelLiteral, ch) for ch in rule.channels],
        quiet_hours_start=(
            rule.quiet_hours_start.strftime("%H:%M") if rule.quiet_hours_start else None
        ),
        quiet_hours_end=(rule.quiet_hours_end.strftime("%H:%M") if rule.quiet_hours_end else None),
        cooldown_minutes=rule.cooldown_minutes,
        timezone=rule.timezone,
        is_enabled=rule.is_enabled,
        last_triggered_at=(ensure_utc(rule.last_triggered_at) if rule.last_triggered_at else None),
        created_at=ensure_utc(rule.created_at),
    )


def serialize_notification(notif: Notification) -> NotificationSchema:
    """Convert a `Notification` ORM entity and its deliveries into an API response DTO."""
    return NotificationSchema(
        id=notif.id,
        alert_rule_id=notif.alert_rule_id,
        title=notif.title,
        body=notif.body,
        severity=cast(NotificationSeverityLiteral, notif.severity),
        dedup_key=notif.dedup_key,
        read_at=ensure_utc(notif.read_at) if notif.read_at else None,
        created_at=ensure_utc(notif.created_at),
        deliveries=[
            NotificationDeliverySchema(
                id=d.id,
                channel=cast(AlertChannelLiteral, d.channel),
                status=cast(DeliveryStatusLiteral, d.status),
                provider_message_id=d.provider_message_id,
                attempt_count=d.attempt_count,
                delivered_at=ensure_utc(d.delivered_at) if d.delivered_at else None,
            )
            for d in notif.deliveries
        ],
    )
