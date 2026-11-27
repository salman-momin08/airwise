from __future__ import annotations

import uuid
from datetime import UTC, datetime, time

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, ResourceNotFoundError
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
from app.models.identity import User, UserProfile


class AlertsCommunityRepository:
    """Async SQLAlchemy 2.x repository enforcing strict user scoping & community privacy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_alert_rules_for_user(self, *, user_id: uuid.UUID) -> list[AlertRule]:
        rows = await self._session.scalars(
            select(AlertRule)
            .where(AlertRule.user_id == user_id)
            .order_by(AlertRule.created_at.desc())
        )
        return list(rows.all())

    async def list_enabled_alert_rules(
        self, *, user_id: uuid.UUID | None = None
    ) -> list[AlertRule]:
        stmt = select(AlertRule).where(AlertRule.is_enabled.is_(True))
        if user_id is not None:
            stmt = stmt.where(AlertRule.user_id == user_id)
        rows = await self._session.scalars(stmt.order_by(AlertRule.created_at.asc()))
        return list(rows.all())

    async def require_alert_rule(
        self, *, user_id: uuid.UUID, rule_id: uuid.UUID
    ) -> AlertRule:
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

    # --- Community & Moderation Queries ---

    async def list_communities(self, *, city: str | None = None) -> list[Community]:
        stmt = select(Community).order_by(Community.city.asc(), Community.name.asc())
        if city is not None:
            stmt = stmt.where(func.lower(Community.city) == city.strip().lower())
        rows = await self._session.scalars(stmt)
        return list(rows.all())

    async def require_community(self, community_id: uuid.UUID) -> Community:
        comm = await self._session.scalar(
            select(Community).where(Community.id == community_id)
        )
        if comm is None:
            raise ResourceNotFoundError("Community group was not found.")
        return comm

    async def create_community(
        self,
        *,
        slug: str,
        name: str,
        city: str,
        coarse_boundary_label: str,
        description: str,
        moderation_policy: str,
        created_by: uuid.UUID,
    ) -> Community:
        existing = await self._session.scalar(
            select(Community).where(func.lower(Community.slug) == slug.lower())
        )
        if existing is not None:
            raise ConflictError("A community group with this slug already exists.")
        comm = Community(
            id=uuid.uuid4(),
            slug=slug.lower(),
            name=name,
            city=city,
            coarse_boundary_label=coarse_boundary_label,
            description=description,
            moderation_policy=moderation_policy,
            created_by=created_by,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(comm)
        await self._session.flush()
        return comm

    async def get_membership(
        self, *, community_id: uuid.UUID, user_id: uuid.UUID
    ) -> CommunityMember | None:
        return await self._session.scalar(
            select(CommunityMember).where(
                CommunityMember.community_id == community_id,
                CommunityMember.user_id == user_id,
            )
        )

    async def upsert_membership(
        self,
        *,
        community_id: uuid.UUID,
        user_id: uuid.UUID,
        public_display_consent: bool,
        role: str = "member",
    ) -> CommunityMember:
        member = await self.get_membership(community_id=community_id, user_id=user_id)
        if member is None:
            member = CommunityMember(
                community_id=community_id,
                user_id=user_id,
                role=role,
                public_display_consent=public_display_consent,
                joined_at=datetime.now(tz=UTC),
            )
            self._session.add(member)
        else:
            member.public_display_consent = public_display_consent
        await self._session.flush()
        return member

    async def remove_membership(
        self, *, community_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        await self._session.execute(
            delete(CommunityMember).where(
                CommunityMember.community_id == community_id,
                CommunityMember.user_id == user_id,
            )
        )

    async def count_members(self, community_id: uuid.UUID) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(CommunityMember)
            .where(CommunityMember.community_id == community_id)
        )
        return int(count or 0)

    async def count_members_batch(
        self, community_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, int]:
        if not community_ids:
            return {}
        rows = (
            await self._session.execute(
                select(CommunityMember.community_id, func.count())
                .where(CommunityMember.community_id.in_(community_ids))
                .group_by(CommunityMember.community_id)
            )
        ).all()
        return {comm_id: int(cnt or 0) for comm_id, cnt in rows}

    async def count_active_initiatives_batch(
        self, community_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, int]:
        if not community_ids:
            return {}
        rows = (
            await self._session.execute(
                select(CommunityInitiative.community_id, func.count())
                .where(
                    CommunityInitiative.community_id.in_(community_ids),
                    CommunityInitiative.moderation_status == "active",
                )
                .group_by(CommunityInitiative.community_id)
            )
        ).all()
        return {comm_id: int(cnt or 0) for comm_id, cnt in rows}

    async def get_memberships_batch(
        self, *, community_ids: set[uuid.UUID], user_id: uuid.UUID
    ) -> dict[uuid.UUID, CommunityMember]:
        if not community_ids:
            return {}
        rows = await self._session.scalars(
            select(CommunityMember).where(
                CommunityMember.community_id.in_(community_ids),
                CommunityMember.user_id == user_id,
            )
        )
        return {member.community_id: member for member in rows.all()}

    async def list_consented_member_names(self, community_id: uuid.UUID) -> list[str]:
        """Strictly returns display_name ONLY for members with public_display_consent=True."""
        stmt = (
            select(UserProfile.display_name)
            .join(User, User.id == UserProfile.user_id)
            .join(CommunityMember, CommunityMember.user_id == User.id)
            .where(
                CommunityMember.community_id == community_id,
                CommunityMember.public_display_consent.is_(True),
                User.deleted_at.is_(None),
            )
            .order_by(CommunityMember.joined_at.asc())
            .limit(50)
        )
        rows = await self._session.scalars(stmt)
        return list(rows.all())

    async def create_initiative(
        self,
        *,
        community_id: uuid.UUID,
        title: str,
        description: str,
        challenge_type: str,
        starts_at: datetime,
        ends_at: datetime,
        created_by: uuid.UUID,
    ) -> CommunityInitiative:
        item = CommunityInitiative(
            id=uuid.uuid4(),
            community_id=community_id,
            title=title,
            description=description,
            challenge_type=challenge_type,
            starts_at=starts_at,
            ends_at=ends_at,
            moderation_status="active",
            created_by=created_by,
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def require_initiative(self, initiative_id: uuid.UUID) -> CommunityInitiative:
        item = await self._session.scalar(
            select(CommunityInitiative).where(CommunityInitiative.id == initiative_id)
        )
        if item is None:
            raise ResourceNotFoundError("Community initiative was not found.")
        return item

    async def list_initiatives(
        self,
        *,
        community_id: uuid.UUID | None = None,
        city: str | None = None,
        include_non_active: bool = False,
    ) -> list[CommunityInitiative]:
        stmt = select(CommunityInitiative).join(
            Community, Community.id == CommunityInitiative.community_id
        )
        if community_id is not None:
            stmt = stmt.where(CommunityInitiative.community_id == community_id)
        if city is not None:
            stmt = stmt.where(func.lower(Community.city) == city.strip().lower())
        if not include_non_active:
            stmt = stmt.where(CommunityInitiative.moderation_status == "active")
        stmt = stmt.order_by(CommunityInitiative.starts_at.desc())
        rows = await self._session.scalars(stmt)
        return list(rows.all())

    async def log_participation(
        self,
        *,
        initiative_id: uuid.UUID,
        user_id: uuid.UUID,
        actions_count: int,
        avoided_co2e_kg: float,
        note: str | None,
    ) -> CommunityParticipation:
        entry = CommunityParticipation(
            id=uuid.uuid4(),
            initiative_id=initiative_id,
            user_id=user_id,
            self_reported_actions_count=actions_count,
            estimated_avoided_co2e_kg=round(avoided_co2e_kg, 4),
            note=note,
            moderation_status="approved",
            reported_at=datetime.now(tz=UTC),
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def aggregate_initiative_metrics(
        self, initiative_id: uuid.UUID
    ) -> tuple[int, int, float]:
        row = (
            await self._session.execute(
                select(
                    func.count(CommunityParticipation.id),
                    func.coalesce(
                        func.sum(CommunityParticipation.self_reported_actions_count), 0
                    ),
                    func.coalesce(
                        func.sum(CommunityParticipation.estimated_avoided_co2e_kg), 0.0
                    ),
                ).where(
                    CommunityParticipation.initiative_id == initiative_id,
                    CommunityParticipation.moderation_status == "approved",
                )
            )
        ).one()
        return int(row[0] or 0), int(row[1] or 0), round(float(row[2] or 0.0), 4)

    async def aggregate_initiatives_metrics_batch(
        self, initiative_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[int, int, float]]:
        if not initiative_ids:
            return {}
        rows = (
            await self._session.execute(
                select(
                    CommunityParticipation.initiative_id,
                    func.count(CommunityParticipation.id),
                    func.coalesce(
                        func.sum(CommunityParticipation.self_reported_actions_count), 0
                    ),
                    func.coalesce(
                        func.sum(CommunityParticipation.estimated_avoided_co2e_kg), 0.0
                    ),
                )
                .where(
                    CommunityParticipation.initiative_id.in_(initiative_ids),
                    CommunityParticipation.moderation_status == "approved",
                )
                .group_by(CommunityParticipation.initiative_id)
            )
        ).all()
        return {
            init_id: (int(entries or 0), int(actions or 0), round(float(co2e or 0.0), 4))
            for init_id, entries, actions, co2e in rows
        }

    async def aggregate_community_metrics(
        self, community_id: uuid.UUID
    ) -> tuple[int, float]:
        row = (
            await self._session.execute(
                select(
                    func.coalesce(
                        func.sum(CommunityParticipation.self_reported_actions_count), 0
                    ),
                    func.coalesce(
                        func.sum(CommunityParticipation.estimated_avoided_co2e_kg), 0.0
                    ),
                )
                .join(
                    CommunityInitiative,
                    CommunityInitiative.id == CommunityParticipation.initiative_id,
                )
                .where(
                    CommunityInitiative.community_id == community_id,
                    CommunityInitiative.moderation_status == "active",
                    CommunityParticipation.moderation_status == "approved",
                )
            )
        ).one()
        return int(row[0] or 0), round(float(row[1] or 0.0), 4)

    async def create_abuse_report(
        self,
        *,
        community_id: uuid.UUID,
        initiative_id: uuid.UUID | None,
        reporter_user_id: uuid.UUID,
        reason_category: str,
        details: str,
    ) -> CommunityAbuseReport:
        report = CommunityAbuseReport(
            id=uuid.uuid4(),
            community_id=community_id,
            initiative_id=initiative_id,
            reporter_user_id=reporter_user_id,
            reason_category=reason_category,
            details=details,
            status="open",
            created_at=datetime.now(tz=UTC),
        )
        self._session.add(report)
        await self._session.flush()
        return report

    async def list_abuse_reports(
        self, *, status: str | None = None
    ) -> list[CommunityAbuseReport]:
        stmt = select(CommunityAbuseReport).order_by(CommunityAbuseReport.created_at.desc())
        if status is not None:
            stmt = stmt.where(CommunityAbuseReport.status == status)
        rows = await self._session.scalars(stmt.limit(200))
        return list(rows.all())

    async def require_abuse_report(self, report_id: uuid.UUID) -> CommunityAbuseReport:
        report = await self._session.scalar(
            select(CommunityAbuseReport).where(CommunityAbuseReport.id == report_id)
        )
        if report is None:
            raise ResourceNotFoundError("Moderation report was not found.")
        return report

    async def erase_and_anonymize_user_data(self, *, user_id: uuid.UUID) -> None:
        """Deletes private alerts/notifications/memberships and anonymizes community aggregates."""
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
            update(Community)
            .where(Community.created_by == user_id)
            .values(created_by=None)
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
