"""Smart AQI alert rule management, quiet-hour suppression, and multi-channel dispatch."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ExternalProviderUnavailableError, ResourceNotFoundError
from app.integrations.email.provider import (
    EmailProvider,
    TransactionalEmailMessage,
    get_email_provider,
)
from app.models.community_alerts import AlertRule
from app.models.identity import User
from app.repositories.alerts_repository import AlertsRepository
from app.repositories.identity_repository import IdentityRepository
from app.schemas.air_quality import CurrentAirQualitySchema
from app.schemas.alerts import (
    AlertEvaluationSummarySchema,
    AlertRuleSchema,
    CreateAlertRuleRequest,
    NotificationSchema,
    UpdateAlertRuleRequest,
)
from app.services.air_quality.aqi_calculator import AQIStandard
from app.services.air_quality.telemetry_service import AirQualityTelemetryService
from app.services.alerts.deduplicator import (
    AlertDeduplicator,
    alert_deduplicator,
    ensure_utc,
    is_within_quiet_hours,
    parse_hhmm_optional,
    serialize_alert_rule,
    serialize_notification,
)
from app.services.alerts.rule_evaluator import (
    evaluate_rule_condition,
    resolve_rule_telemetry,
)
from app.services.weather.weather_service import WeatherTelemetryService


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
        self._repo = AlertsRepository(session)
        self._identity_repo = IdentityRepository(session)
        self._email = email_provider or get_email_provider()

    async def list_rules(self, *, user_id: uuid.UUID) -> list[AlertRuleSchema]:
        """List all alert rules configured by `user_id`."""
        rows = await self._repo.list_alert_rules_for_user(user_id=user_id)
        return [serialize_alert_rule(r) for r in rows]

    async def create_rule(
        self, *, user_id: uuid.UUID, payload: CreateAlertRuleRequest
    ) -> AlertRuleSchema:
        """Create a new AQI alert rule resolving optional saved-location coordinates/timezone."""
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
            quiet_hours_start=parse_hhmm_optional(payload.quiet_hours_start),
            quiet_hours_end=parse_hhmm_optional(payload.quiet_hours_end),
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
        """Update mutable threshold, channel, quiet-hour, or enabled settings on a rule."""
        rule = await self._repo.require_alert_rule(user_id=user_id, rule_id=rule_id)
        if payload.threshold_value is not None:
            rule.threshold_value = payload.threshold_value
        if payload.channels is not None:
            rule.channels = list(dict.fromkeys(payload.channels))
        if payload.clear_quiet_hours:
            rule.quiet_hours_start = None
            rule.quiet_hours_end = None
        elif payload.quiet_hours_start is not None and payload.quiet_hours_end is not None:
            rule.quiet_hours_start = parse_hhmm_optional(payload.quiet_hours_start)
            rule.quiet_hours_end = parse_hhmm_optional(payload.quiet_hours_end)
        if payload.cooldown_minutes is not None:
            rule.cooldown_minutes = payload.cooldown_minutes
        if payload.timezone is not None:
            rule.timezone = payload.timezone
        if payload.is_enabled is not None:
            rule.is_enabled = payload.is_enabled

        await self._session.commit()
        return serialize_alert_rule(rule)

    async def delete_rule(self, *, user_id: uuid.UUID, rule_id: uuid.UUID) -> None:
        """Delete a user-owned alert rule."""
        await self._repo.delete_alert_rule(user_id=user_id, rule_id=rule_id)
        await self._session.commit()

    async def unsubscribe_all(self, *, user_id: uuid.UUID) -> int:
        """Disable all enabled alert rules for `user_id`."""
        disabled = await self._repo.disable_all_alert_rules_for_user(user_id=user_id)
        await self._session.commit()
        return disabled

    async def list_notifications(
        self, *, user_id: uuid.UUID, limit: int = 50
    ) -> list[NotificationSchema]:
        """Return recent in-app notifications and delivery statuses for `user_id`."""
        rows = await self._repo.list_notifications_for_user(user_id=user_id, limit=limit)
        return [serialize_notification(n) for n in rows]

    async def mark_read(
        self, *, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> NotificationSchema:
        """Mark a single notification read."""
        notif = await self._repo.mark_notification_read(
            user_id=user_id, notification_id=notification_id
        )
        await self._session.commit()
        return serialize_notification(notif)

    async def mark_all_read(self, *, user_id: uuid.UUID) -> int:
        """Mark all unread notifications read for `user_id`."""
        count = await self._repo.mark_all_notifications_read(user_id=user_id)
        await self._session.commit()
        return count

    async def _dispatch_rule_channels(
        self,
        *,
        rule: AlertRule,
        user: User | None,
        title: str,
        body: str,
        in_quiet: bool,
        eval_now: datetime,
    ) -> tuple[list[tuple[str, str, str | None, datetime | None]], int]:
        deliveries: list[tuple[str, str, str | None, datetime | None]] = []
        quiet_suppressed = 0
        for ch in rule.channels:
            if in_quiet and ch in {"email", "web_push", "in_app"}:
                deliveries.append(
                    (ch, "suppressed_quiet_hours", "in-app-inbox" if ch == "in_app" else None, None)
                )
                quiet_suppressed += 1
            elif ch == "in_app":
                deliveries.append((ch, "sent", "in-app-inbox", eval_now))
            elif ch == "email":
                deliveries.append(
                    await self._deliver_email_channel(
                        user=user, title=title, body=body, eval_now=eval_now
                    )
                )
            elif ch == "web_push":
                deliveries.append((ch, "unconfigured_channel", None, None))
        return deliveries, quiet_suppressed

    async def _deliver_email_channel(
        self,
        *,
        user: User | None,
        title: str,
        body: str,
        eval_now: datetime,
    ) -> tuple[str, str, str | None, datetime | None]:
        if user is None or not user.email:
            return ("email", "failed", None, None)
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
            return ("email", "sent", msg_id, eval_now)
        except ExternalProviderUnavailableError:
            return ("email", "failed", None, None)

    @staticmethod
    def _is_within_cooldown(rule: AlertRule, eval_now: datetime) -> bool:
        if rule.last_triggered_at is None:
            return False
        elapsed = eval_now - ensure_utc(rule.last_triggered_at)
        return elapsed < timedelta(minutes=rule.cooldown_minutes)

    async def _should_suppress_triggered_rule(
        self, *, rule: AlertRule, state_sig: str, eval_now: datetime
    ) -> tuple[bool, str]:
        dedup_key = f"alert:{rule.id}:{state_sig}"
        if rule.last_dedup_state == state_sig or self._is_within_cooldown(rule, eval_now):
            return True, dedup_key
        acquired = await alert_deduplicator.acquire(
            settings=self._settings,
            dedup_key=dedup_key,
            ttl_seconds=rule.cooldown_minutes * 60,
        )
        return (not acquired), dedup_key

    async def evaluate_active_rules(
        self,
        *,
        user_id: uuid.UUID | None = None,
        evaluation_time: datetime | None = None,
    ) -> AlertEvaluationSummarySchema:
        """Evaluate enabled alert rules with memoized telemetry, deduplication, and quiet hours."""
        eval_now = ensure_utc(evaluation_time or datetime.now(tz=UTC))
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
        current_memo: dict[tuple[str, AQIStandard], CurrentAirQualitySchema | None] = {}
        forecast_max_memo: dict[tuple[str, AQIStandard], int | None] = {}
        inversion_memo: dict[str, bool] = {}
        users_memo: dict[uuid.UUID, User | None] = {}

        triggered_count = 0
        suppressed_dedup_count = 0
        suppressed_quiet_count = 0

        for rule in rules:
            std = (
                AQIStandard.US_EPA
                if rule.aqi_standard == AQIStandard.US_EPA.value
                else AQIStandard.INDIA_NAQI
            )
            current, max_fc_aqi, inv_risk = await resolve_rule_telemetry(
                rule=rule,
                std=std,
                aq_service=aq_service,
                wx_service=wx_service,
                current_memo=current_memo,
                forecast_max_memo=forecast_max_memo,
                inversion_memo=inversion_memo,
            )

            fired, state_sig, title, body, severity = evaluate_rule_condition(
                rule=rule,
                standard=std,
                aqi=current.aqi if current is not None else None,
                category=current.category if current is not None else None,
                is_available=bool(
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

            suppressed, dedup_key = await self._should_suppress_triggered_rule(
                rule=rule, state_sig=state_sig, eval_now=eval_now
            )
            if suppressed:
                suppressed_dedup_count += 1
                continue

            if rule.user_id not in users_memo:
                users_memo[rule.user_id] = await self._identity_repo.get_user_by_id(rule.user_id)

            deliveries, quiet_cnt = await self._dispatch_rule_channels(
                rule=rule,
                user=users_memo[rule.user_id],
                title=title,
                body=body,
                in_quiet=is_within_quiet_hours(
                    utc_now=eval_now,
                    timezone_name=rule.timezone,
                    quiet_start=rule.quiet_hours_start,
                    quiet_end=rule.quiet_hours_end,
                ),
                eval_now=eval_now,
            )
            suppressed_quiet_count += quiet_cnt

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


__all__ = [
    "AlertDeduplicator",
    "SmartAlertService",
    "alert_deduplicator",
    "is_within_quiet_hours",
    "serialize_alert_rule",
    "serialize_notification",
]
