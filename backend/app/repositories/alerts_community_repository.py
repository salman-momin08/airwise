"""Composite repository combining user-scoped alerts, community privacy, and GDPR portability."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, or_, select, update

from app.models.community_alerts import (
    AlertRule,
    Community,
    CommunityAbuseReport,
    CommunityInitiative,
    CommunityMember,
    CommunityParticipation,
    Notification,
    NotificationDelivery,
)
from app.repositories.alerts_repository import AlertsRepository
from app.repositories.community_repository import CommunityRepository


class AlertsCommunityRepository(AlertsRepository, CommunityRepository):
    """Unified repository facade supporting alerts, communities, export, and right-to-erasure."""

    async def erase_and_anonymize_user_data(self, *, user_id: uuid.UUID) -> None:
        """Delete private alerts/notifications/memberships and anonymize community aggregates."""
        user_rules = select(AlertRule.id).where(AlertRule.user_id == user_id)
        user_notifs = select(Notification.id).where(
            or_(Notification.user_id == user_id, Notification.alert_rule_id.in_(user_rules))
        )
        await self._session.execute(
            delete(NotificationDelivery).where(
                NotificationDelivery.notification_id.in_(user_notifs)
            )
        )
        await self._session.execute(
            delete(Notification).where(
                or_(
                    Notification.user_id == user_id,
                    Notification.alert_rule_id.in_(user_rules),
                )
            )
        )
        await self._session.execute(delete(AlertRule).where(AlertRule.user_id == user_id))
        await self._session.execute(
            delete(CommunityMember).where(CommunityMember.user_id == user_id)
        )
        # Anonymize aggregate participation & moderation references
        await self._session.execute(
            update(CommunityParticipation)
            .where(CommunityParticipation.user_id == user_id)
            .values(user_id=None, note=None)
        )
        await self._session.execute(
            update(Community).where(Community.created_by == user_id).values(created_by=None)
        )
        await self._session.execute(
            update(CommunityInitiative)
            .where(CommunityInitiative.created_by == user_id)
            .values(created_by=None)
        )
        await self._session.execute(
            update(CommunityAbuseReport)
            .where(CommunityAbuseReport.reporter_user_id == user_id)
            .values(reporter_user_id=None)
        )
        await self._session.execute(
            update(CommunityAbuseReport)
            .where(CommunityAbuseReport.resolved_by == user_id)
            .values(resolved_by=None)
        )

    async def export_user_data(
        self, *, user_id: uuid.UUID
    ) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
        """Export user-owned alert rules, notifications, and community memberships."""
        rules = await self.list_alert_rules_for_user(user_id=user_id)
        rule_items: list[dict[str, object]] = [
            {
                "id": str(r.id),
                "city": r.city,
                "alert_type": r.alert_type,
                "aqi_standard": r.aqi_standard,
                "threshold_value": r.threshold_value,
                "channels": list(r.channels),
                "quiet_hours_start": (
                    r.quiet_hours_start.strftime("%H:%M") if r.quiet_hours_start else None
                ),
                "quiet_hours_end": (
                    r.quiet_hours_end.strftime("%H:%M") if r.quiet_hours_end else None
                ),
                "cooldown_minutes": r.cooldown_minutes,
                "timezone": r.timezone,
                "is_enabled": r.is_enabled,
                "created_at": r.created_at.isoformat(),
            }
            for r in rules
        ]
        notifs = await self.list_notifications_for_user(user_id=user_id, limit=500)
        notif_items: list[dict[str, object]] = [
            {
                "id": str(n.id),
                "title": n.title,
                "body": n.body,
                "severity": n.severity,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifs
        ]
        memberships = await self._session.execute(
            select(CommunityMember, Community.name, Community.city)
            .join(Community, Community.id == CommunityMember.community_id)
            .where(CommunityMember.user_id == user_id)
        )
        member_items: list[dict[str, object]] = [
            {
                "community_id": str(m.community_id),
                "community_name": comm_name,
                "city": comm_city,
                "role": m.role,
                "public_display_consent": m.public_display_consent,
                "joined_at": m.joined_at.isoformat(),
            }
            for m, comm_name, comm_city in memberships
        ]
        return rule_items, notif_items, member_items


__all__ = ["AlertsCommunityRepository", "AlertsRepository", "CommunityRepository"]
