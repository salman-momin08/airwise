"""Async SQLAlchemy 2.x repository for user-scoped AQI alert rules and notifications."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ResourceNotFoundError
from app.models.community_alerts import AlertRule, Notification, NotificationDelivery


class AlertsRepository:
    """Persist and query user-owned `alert_rules`, `notifications`, and deliveries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_alert_rules_for_user(self, *, user_id: uuid.UUID) -> list[AlertRule]:
        """Return all alert rules owned by `user_id`, newest first."""
        rows = await self._session.scalars(
            select(AlertRule)
            .where(AlertRule.user_id == user_id)
            .order_by(AlertRule.created_at.desc())
        )
        return list(rows.all())

    async def list_enabled_alert_rules(
        self, *, user_id: uuid.UUID | None = None
    ) -> list[AlertRule]:
        """Return active alert rules, optionally scoped to a single user."""
        stmt = select(AlertRule).where(AlertRule.is_enabled.is_(True))
        if user_id is not None:
            stmt = stmt.where(AlertRule.user_id == user_id)
        rows = await self._session.scalars(stmt.order_by(AlertRule.created_at.asc()))
        return list(rows.all())

    async def require_alert_rule(self, *, user_id: uuid.UUID, rule_id: uuid.UUID) -> AlertRule:
        """Fetch an alert rule enforcing object-level ownership or raise 404."""
        rule = await self._session.scalar(
            select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == user_id)
        )
        if rule is None:
            raise ResourceNotFoundError("Alert rule was not found.")
        return rule

    async def create_alert_rule(
        self,
        *,
        user_id: uuid.UUID,
        location_id: uuid.UUID | None,
        city: str,
        alert_type: str,
        aqi_standard: str,
        threshold_value: int | None,
        channels: list[str],
        quiet_hours_start: time | None,
        quiet_hours_end: time | None,
        cooldown_minutes: int,
        timezone: str,
        is_enabled: bool,
    ) -> AlertRule:
        """Create and flush a new user-scoped AQI alert rule."""
        rule = AlertRule(
            id=uuid.uuid4(),
            user_id=user_id,
            location_id=location_id,
            city=city,
            alert_type=alert_type,
            aqi_standard=aqi_standard,
            threshold_value=threshold_value,
            channels=channels,
            quiet_hours_start=quiet_hours_start,
            quiet_hours_end=quiet_hours_end,
            cooldown_minutes=cooldown_minutes,
            timezone=timezone,
            is_enabled=is_enabled,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def delete_alert_rule(self, *, user_id: uuid.UUID, rule_id: uuid.UUID) -> None:
        """Delete an alert rule while preserving historical notifications."""
        rule = await self.require_alert_rule(user_id=user_id, rule_id=rule_id)
        await self._session.execute(
            update(Notification)
            .where(Notification.alert_rule_id == rule.id)
            .values(alert_rule_id=None)
        )
        await self._session.execute(
            delete(AlertRule).where(AlertRule.id == rule.id, AlertRule.user_id == user_id)
        )

    async def disable_all_alert_rules_for_user(self, *, user_id: uuid.UUID) -> int:
        """Disable all currently enabled alert rules for `user_id`."""
        rules = await self.list_enabled_alert_rules(user_id=user_id)
        for rule in rules:
            rule.is_enabled = False
        await self._session.flush()
        return len(rules)

    async def create_notification_with_deliveries(
        self,
        *,
        user_id: uuid.UUID,
        alert_rule_id: uuid.UUID | None,
        title: str,
        body: str,
        severity: str,
        dedup_key: str,
        created_at: datetime,
        deliveries: list[tuple[str, str, str | None, datetime | None]],
    ) -> Notification:
        """Persist a triggered notification alongside per-channel delivery records."""
        notif = Notification(
            id=uuid.uuid4(),
            user_id=user_id,
            alert_rule_id=alert_rule_id,
            title=title,
            body=body,
            severity=severity,
            dedup_key=dedup_key,
            created_at=created_at,
        )
        self._session.add(notif)
        await self._session.flush()
        for channel, status, provider_msg_id, delivered_at in deliveries:
            self._session.add(
                NotificationDelivery(
                    id=uuid.uuid4(),
                    notification_id=notif.id,
                    channel=channel,
                    status=status,
                    provider_message_id=provider_msg_id,
                    attempt_count=1,
                    delivered_at=delivered_at,
                )
            )
        await self._session.flush()
        return notif

    async def list_notifications_for_user(
        self, *, user_id: uuid.UUID, limit: int = 50
    ) -> list[Notification]:
        """List notifications and eager-loaded channel deliveries for `user_id`."""
        rows = await self._session.scalars(
            select(Notification)
            .execution_options(populate_existing=True)
            .options(selectinload(Notification.deliveries))
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list(rows.all())

    async def mark_notification_read(
        self, *, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification:
        """Mark a single user-owned notification as read."""
        notif = await self._session.scalar(
            select(Notification)
            .options(selectinload(Notification.deliveries))
            .where(Notification.id == notification_id, Notification.user_id == user_id)
        )
        if notif is None:
            raise ResourceNotFoundError("Notification was not found.")
        if notif.read_at is None:
            notif.read_at = datetime.now(tz=UTC)
            await self._session.flush()
        return notif

    async def mark_all_notifications_read(self, *, user_id: uuid.UUID) -> int:
        """Mark all unread notifications for `user_id` as read."""
        unread = list(
            await self._session.scalars(
                select(Notification).where(
                    Notification.user_id == user_id, Notification.read_at.is_(None)
                )
            )
        )
        now = datetime.now(tz=UTC)
        for item in unread:
            item.read_at = now
        await self._session.flush()
        return len(unread)
