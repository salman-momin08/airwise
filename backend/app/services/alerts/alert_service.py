from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError, ResourceNotFoundError
from app.core.redis_client import create_async_redis_client
from app.integrations.email.provider import (
    EmailProvider,
    TransactionalEmailMessage,
    get_email_provider,
)
from app.models.community_alerts import AlertRule, Notification
from app.repositories.alerts_community_repository import AlertsCommunityRepository
from app.repositories.identity_repository import IdentityRepository
from app.schemas.alerts import (
    AlertChannelLiteral,
    AlertEvaluationSummarySchema,
    AlertRuleSchema,
    AlertTypeLiteral,
    CreateAlertRuleRequest,
    DeliveryStatusLiteral,
    NotificationDeliverySchema,
    NotificationSchema,
    NotificationSeverityLiteral,
    UpdateAlertRuleRequest,
)
from app.services.air_quality.aqi_calculator import AQIStandard
from app.services.air_quality.telemetry_service import AirQualityTelemetryService
from app.services.weather.weather_service import WeatherTelemetryService

logger = structlog.get_logger(__name__)


def _parse_hhmm_optional(value: str | None) -> time | None:
    if value is None:
        return None
    parts = value.split(":")
    return time(hour=int(parts[0]), minute=int(parts[1]))


def _ensure_utc(value: datetime) -> datetime:
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

    local_dt = _ensure_utc(utc_now).astimezone(tz)
    local_clock = time(hour=local_dt.hour, minute=local_dt.minute)
    if quiet_start < quiet_end:
        return quiet_start <= local_clock < quiet_end
    return local_clock >= quiet_start or local_clock < quiet_end


class AlertDeduplicator:
    """Redis SET-NX deduplicator with resilient in-memory fallback for tests/local dev."""

    def __init__(self) -> None:
        self._local_keys: dict[str, float] = {}

    def reset_local_state(self) -> None:
        self._local_keys.clear()

    async def acquire(
        self, *, settings: Settings, dedup_key: str, ttl_seconds: int
    ) -> bool:
        now_ts = datetime.now(tz=UTC).timestamp()
        expired = [k for k, exp in self._local_keys.items() if exp <= now_ts]
        for k in expired:
            self._local_keys.pop(k, None)

        if settings.app_env != "test" and settings.redis_url:
            try:
                async with create_async_redis_client(
                    settings.redis_url,
                    decode_responses=True,
                ) as redis:
                    acquired = await redis.set(dedup_key, "1", ex=max(ttl_seconds, 60), nx=True)
                    return bool(acquired)
            except (RedisError, ValueError, RuntimeError) as exc:
                logger.warning("alert_dedup_redis_fallback", error_type=type(exc).__name__)

        if dedup_key in self._local_keys:
            return False
        self._local_keys[dedup_key] = now_ts + max(ttl_seconds, 60)
        return True


alert_deduplicator = AlertDeduplicator()


def serialize_alert_rule(rule: AlertRule) -> AlertRuleSchema:
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
        quiet_hours_end=(
            rule.quiet_hours_end.strftime("%H:%M") if rule.quiet_hours_end else None
        ),
        cooldown_minutes=rule.cooldown_minutes,
        timezone=rule.timezone,
        is_enabled=rule.is_enabled,
        last_triggered_at=(
            _ensure_utc(rule.last_triggered_at) if rule.last_triggered_at else None
        ),
        created_at=_ensure_utc(rule.created_at),
    )


def serialize_notification(notif: Notification) -> NotificationSchema:
    return NotificationSchema(
        id=notif.id,
        alert_rule_id=notif.alert_rule_id,
        title=notif.title,
        body=notif.body,
        severity=cast(NotificationSeverityLiteral, notif.severity),
        dedup_key=notif.dedup_key,
        read_at=_ensure_utc(notif.read_at) if notif.read_at else None,
        created_at=_ensure_utc(notif.created_at),
        deliveries=[
            NotificationDeliverySchema(
                id=d.id,
                channel=cast(AlertChannelLiteral, d.channel),
                status=cast(DeliveryStatusLiteral, d.status),
                provider_message_id=d.provider_message_id,
                attempt_count=d.attempt_count,
                delivered_at=_ensure_utc(d.delivered_at) if d.delivered_at else None,
            )
            for d in notif.deliveries
        ],
    )


class SmartAlertService:
    """Service managing user AQI alert rules, quiet hours, cooldowns, and notifications."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        email_provider: EmailProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._repo = AlertsCommunityRepository(session)
        self._identity_repo = IdentityRepository(session)
        self._email = email_provider or get_email_provider()

    async def list_rules(self, *, user_id: uuid.UUID) -> list[AlertRuleSchema]:
        rows = await self._repo.list_alert_rules_for_user(user_id=user_id)
        return [serialize_alert_rule(r) for r in rows]

    async def create_rule(
        self, *, user_id: uuid.UUID, payload: CreateAlertRuleRequest
    ) -> AlertRuleSchema:
        city = payload.city
        timezone_name = payload.timezone
        if payload.location_id is not None:
            saved_loc = await self._identity_repo.get_saved_location_for_user(
                user_id=user_id, location_id=payload.location_id
            )
            if saved_loc is None:
                raise ResourceNotFoundError("Saved location was not found.")
            city = saved_loc.city
            timezone_name = saved_loc.timezone

        default_threshold = payload.threshold_value
        if default_threshold is None and payload.alert_type == "clean_air_window":
            default_threshold = 100

        rule = await self._repo.create_alert_rule(
            user_id=user_id,
            location_id=payload.location_id,
            city=city,
            alert_type=payload.alert_type,
            aqi_standard=payload.aqi_standard.value,
            threshold_value=default_threshold,
            channels=list(dict.fromkeys(payload.channels)),
            quiet_hours_start=_parse_hhmm_optional(payload.quiet_hours_start),
            quiet_hours_end=_parse_hhmm_optional(payload.quiet_hours_end),
            cooldown_minutes=payload.cooldown_minutes,
            timezone=timezone_name,
            is_enabled=payload.is_enabled,
        )
        await self._session.commit()
        return serialize_alert_rule(rule)

    async def update_rule(
        self,
        *,
        user_id: uuid.UUID,
        rule_id: uuid.UUID,
        payload: UpdateAlertRuleRequest,
    ) -> AlertRuleSchema:
        rule = await self._repo.require_alert_rule(user_id=user_id, rule_id=rule_id)
        if payload.threshold_value is not None:
            rule.threshold_value = payload.threshold_value
        if payload.channels is not None:
            rule.channels = list(dict.fromkeys(payload.channels))
        if payload.clear_quiet_hours:
            rule.quiet_hours_start = None
            rule.quiet_hours_end = None
        elif payload.quiet_hours_start is not None and payload.quiet_hours_end is not None:
            rule.quiet_hours_start = _parse_hhmm_optional(payload.quiet_hours_start)
            rule.quiet_hours_end = _parse_hhmm_optional(payload.quiet_hours_end)
        if payload.cooldown_minutes is not None:
            rule.cooldown_minutes = payload.cooldown_minutes
        if payload.timezone is not None:
            rule.timezone = payload.timezone
        if payload.is_enabled is not None:
            rule.is_enabled = payload.is_enabled

        await self._session.commit()
        return serialize_alert_rule(rule)

    async def delete_rule(self, *, user_id: uuid.UUID, rule_id: uuid.UUID) -> None:
        await self._repo.delete_alert_rule(user_id=user_id, rule_id=rule_id)
        await self._session.commit()

    async def unsubscribe_all(self, *, user_id: uuid.UUID) -> int:
        disabled = await self._repo.disable_all_alert_rules_for_user(user_id=user_id)
        await self._session.commit()
        return disabled

    async def list_notifications(
        self, *, user_id: uuid.UUID, limit: int = 50
    ) -> list[NotificationSchema]:
        rows = await self._repo.list_notifications_for_user(user_id=user_id, limit=limit)
        return [serialize_notification(n) for n in rows]

    async def mark_read(
        self, *, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> NotificationSchema:
        notif = await self._repo.mark_notification_read(
            user_id=user_id, notification_id=notification_id
        )
        await self._session.commit()
        return serialize_notification(notif)

    async def mark_all_read(self, *, user_id: uuid.UUID) -> int:
        count = await self._repo.mark_all_notifications_read(user_id=user_id)
        await self._session.commit()
        return count

    def _evaluate_single_condition(
        self,
        *,
        rule: AlertRule,
        standard: AQIStandard,
        aqi: int | None,
        category: str | None,
        is_available: bool,
        is_stale: bool,
        precaution: str,
        max_forecast_aqi: int | None,
        inversion_risk: bool,
    ) -> tuple[bool, str, str, str, NotificationSeverityLiteral]:
        """Return (triggered, state_signature, title, body, severity)."""
        std_label = "US EPA" if standard == AQIStandard.US_EPA else "India NAQI"
        atype = rule.alert_type

        if atype == "stale_telemetry_warning":
            if not is_available or is_stale:
                stale_tag = "down" if not is_available else "stale"
                sig = f"stale:{rule.city.lower()}:{standard.value}:{stale_tag}"
                return (
                    True,
                    sig,
                    f"Stale or Unavailable Air Telemetry in {rule.city}",
                    (
                        f"Live verified {std_label} station data for {rule.city} is currently "
                        "delayed or unavailable. Avoid assuming outdoor air is clean until fresh "
                        "measurements resume."
                    ),
                    "info",
                )
            return False, "clear", "", "", "info"

        if not is_available or aqi is None:
            return False, "unavailable", "", "", "info"

        if atype == "aqi_threshold":
            cutoff = rule.threshold_value or 200
            if aqi >= cutoff:
                sig = f"threshold:{rule.city.lower()}:{standard.value}:{category}:{aqi}"
                sev: NotificationSeverityLiteral = (
                    "critical"
                    if aqi >= (301 if standard == AQIStandard.INDIA_NAQI else 201)
                    else "warning"
                )
                return (
                    True,
                    sig,
                    f"{rule.city} {std_label} AQI {aqi} ({category}) Breached Threshold ({cutoff})",
                    f"{precaution} Standard: {std_label} (threshold >= {cutoff}).",
                    sev,
                )
            return False, "clear", "", "", "info"

        if atype == "severe_smog_episode":
            severe_cutoff = 301 if standard == AQIStandard.INDIA_NAQI else 201
            if aqi >= severe_cutoff:
                sig = f"severe:{rule.city.lower()}:{standard.value}:{category}:{aqi}"
                return (
                    True,
                    sig,
                    f"Severe Smog Episode in {rule.city}: {std_label} AQI {aqi} ({category})",
                    (
                        f"{precaution} Avoid outdoor cycling, jogging, or prolonged roadside "
                        "exposure; prioritize indoor HEPA filtration."
                    ),
                    "critical",
                )
            return False, "clear", "", "", "info"

        if atype == "forecast_deterioration":
            cutoff = rule.threshold_value or (201 if standard == AQIStandard.INDIA_NAQI else 151)
            if max_forecast_aqi is not None and max_forecast_aqi >= cutoff and aqi < cutoff:
                sig = f"forecast:{rule.city.lower()}:{standard.value}:{max_forecast_aqi}"
                return (
                    True,
                    sig,
                    f"Forecast Smog Deterioration Ahead for {rule.city}",
                    (
                        f"Current {std_label} AQI is {aqi}, but 24h forecast projects up to "
                        f"~{max_forecast_aqi}. Complete errands earlier and seal windows tonight."
                    ),
                    "warning",
                )
            return False, "clear", "", "", "info"

        if atype == "clean_air_window":
            ceiling = rule.threshold_value or 100
            if aqi <= ceiling and not inversion_risk and not is_stale:
                sig = f"clean_window:{rule.city.lower()}:{standard.value}:{category}:{aqi}"
                return (
                    True,
                    sig,
                    f"Cleaner Outdoor Air Window in {rule.city} ({std_label} AQI {aqi})",
                    (
                        f"Verified {std_label} AQI is {aqi} ({category}) without thermal inversion "
                        "stagnation—suitable for 15–20 minutes of cross-ventilation or errands."
                    ),
                    "info",
                )
            return False, "clear", "", "", "info"

        if atype == "daily_digest":
            day_tag = datetime.now(tz=UTC).strftime("%Y-%m-%d")
            sig = f"digest:{rule.city.lower()}:{standard.value}:{day_tag}"
            return (
                True,
                sig,
                f"Daily AirWise Digest · {rule.city} ({std_label} AQI {aqi})",
                f"Current status: {category} ({std_label} AQI {aqi}). {precaution}",
                "info",
            )

        return False, "clear", "", "", "info"

    async def evaluate_active_rules(
        self,
        *,
        user_id: uuid.UUID | None = None,
        evaluation_time: datetime | None = None,
    ) -> AlertEvaluationSummarySchema:
        eval_now = _ensure_utc(evaluation_time or datetime.now(tz=UTC))
        rules = await self._repo.list_enabled_alert_rules(user_id=user_id)
        if not rules:
            return AlertEvaluationSummarySchema(
                evaluated_rules=0,
                triggered_notifications=0,
                suppressed_duplicates_or_cooldown=0,
                suppressed_quiet_hours_deliveries=0,
            )

        aq_service = AirQualityTelemetryService(self._session, self._settings)
        wx_service = WeatherTelemetryService(self._session, self._settings)

        triggered_count = 0
        suppressed_dedup_count = 0
        suppressed_quiet_count = 0

        for rule in rules:
            std = (
                AQIStandard.US_EPA
                if rule.aqi_standard == AQIStandard.US_EPA.value
                else AQIStandard.INDIA_NAQI
            )
            try:
                current = await aq_service.get_current_air_quality(city=rule.city, standard=std)
            except ExternalProviderUnavailableError:
                current = None

            max_fc_aqi: int | None = None
            if rule.alert_type == "forecast_deterioration":
                try:
                    fc = await aq_service.get_air_quality_forecast(
                        city=rule.city, standard=std, hours=24
                    )
                    valid_fc = [p.aqi for p in fc.points if p.aqi is not None]
                    max_fc_aqi = max(valid_fc) if valid_fc else None
                except ExternalProviderUnavailableError:
                    max_fc_aqi = None

            inv_risk = False
            if rule.alert_type == "clean_air_window":
                try:
                    wx = await wx_service.get_current_weather(city=rule.city)
                    inv_risk = bool(wx.inversion_risk_flag)
                except ExternalProviderUnavailableError:
                    inv_risk = False

            fired, state_sig, title, body, severity = self._evaluate_single_condition(
                rule=rule,
                standard=std,
                aqi=current.aqi if current is not None else None,
                category=current.category if current is not None else None,
                is_available=(
                    current is not None
                    and current.status == "available"
                    and current.aqi is not None
                ),
                is_stale=bool(current.is_stale) if current is not None else False,
                precaution=(
                    current.precaution_summary
                    if current is not None
                    else "Verified station reading unavailable."
                ),
                max_forecast_aqi=max_fc_aqi,
                inversion_risk=inv_risk,
            )

            if not fired:
                if state_sig == "clear":
                    rule.last_dedup_state = "clear"
                continue

            # 1. Anti-spam: unchanged AQI state never spams duplicate notifications
            if rule.last_dedup_state == state_sig:
                suppressed_dedup_count += 1
                continue

            # 2. Cooldown window check across fluctuating breaches
            if rule.last_triggered_at is not None:
                elapsed = eval_now - _ensure_utc(rule.last_triggered_at)
                if elapsed < timedelta(minutes=rule.cooldown_minutes):
                    suppressed_dedup_count += 1
                    continue

            dedup_key = f"alert:{rule.id}:{state_sig}"
            acquired = await alert_deduplicator.acquire(
                settings=self._settings,
                dedup_key=dedup_key,
                ttl_seconds=rule.cooldown_minutes * 60,
            )
            if not acquired:
                suppressed_dedup_count += 1
                continue

            in_quiet = is_within_quiet_hours(
                utc_now=eval_now,
                timezone_name=rule.timezone,
                quiet_start=rule.quiet_hours_start,
                quiet_end=rule.quiet_hours_end,
            )

            deliveries: list[tuple[str, str, str | None, datetime | None]] = []
            user = await self._identity_repo.get_user_by_id(rule.user_id)
            for ch in rule.channels:
                if in_quiet and ch in {"email", "web_push"}:
                    deliveries.append((ch, "suppressed_quiet_hours", None, None))
                    suppressed_quiet_count += 1
                elif ch == "in_app":
                    status_str = "suppressed_quiet_hours" if in_quiet else "sent"
                    if in_quiet:
                        suppressed_quiet_count += 1
                    deliveries.append(
                        (ch, status_str, "in-app-inbox", None if in_quiet else eval_now)
                    )
                elif ch == "email":
                    if user is not None and user.email:
                        try:
                            msg_id = await self._email.send_email(
                                TransactionalEmailMessage(
                                    to_email=user.email,
                                    subject=f"[AirWise Alert] {title}",
                                    text_body=(
                                        f"{body}\n\nManage or disable alerts anytime: "
                                        f"{self._settings.frontend_url}/dashboard/alerts"
                                    ),
                                )
                            )
                            deliveries.append((ch, "sent", msg_id, eval_now))
                        except ExternalProviderUnavailableError:
                            deliveries.append((ch, "failed", None, None))
                    else:
                        deliveries.append((ch, "failed", None, None))
                elif ch == "web_push":
                    deliveries.append((ch, "unconfigured_channel", None, None))

            await self._repo.create_notification_with_deliveries(
                user_id=rule.user_id,
                alert_rule_id=rule.id,
                title=title,
                body=body,
                severity=severity,
                dedup_key=dedup_key,
                created_at=eval_now,
                deliveries=deliveries,
            )
            rule.last_triggered_at = eval_now
            rule.last_dedup_state = state_sig
            triggered_count += 1

        await self._session.commit()
        return AlertEvaluationSummarySchema(
            evaluated_rules=len(rules),
            triggered_notifications=triggered_count,
            suppressed_duplicates_or_cooldown=suppressed_dedup_count,
            suppressed_quiet_hours_deliveries=suppressed_quiet_count,
        )
