"""Async SQLAlchemy 2.x repository for neighborhood communities, initiatives, and moderation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ResourceNotFoundError
from app.models.community_alerts import (
    Community,
    CommunityAbuseReport,
    CommunityInitiative,
    CommunityMember,
    CommunityParticipation,
)
from app.models.identity import User, UserProfile


class CommunityRepository:
    """Persist and aggregate neighborhood community groups with consent-gated visibility."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_communities(self, *, city: str | None = None) -> list[Community]:
        """List neighborhood communities ordered by city and name."""
        stmt = select(Community).order_by(Community.city.asc(), Community.name.asc())
        if city is not None:
            stmt = stmt.where(func.lower(Community.city) == city.strip().lower())
        rows = await self._session.scalars(stmt)
        return list(rows.all())

    async def require_community(self, community_id: uuid.UUID) -> Community:
        """Return a community by primary key or raise `ResourceNotFoundError`."""
        comm = await self._session.scalar(select(Community).where(Community.id == community_id))
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
        """Create a neighborhood community group enforcing unique lowercase slugs."""
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
        """Return the user's membership record for `community_id`, if any."""
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
        """Create or update a community membership and its public display consent flag."""
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

    async def remove_membership(self, *, community_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Remove a user's membership from `community_id`."""
        await self._session.execute(
            delete(CommunityMember).where(
                CommunityMember.community_id == community_id,
                CommunityMember.user_id == user_id,
            )
        )

    async def count_members(self, community_id: uuid.UUID) -> int:
        """Count active members belonging to `community_id`."""
        count = await self._session.scalar(
            select(func.count())
            .select_from(CommunityMember)
            .where(CommunityMember.community_id == community_id)
        )
        return int(count or 0)

    async def count_members_batch(self, community_ids: set[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Batch-count community members using a single SQL `GROUP BY` query."""
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
        """Batch-count active initiatives per community using a single `GROUP BY` query."""
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
        """Fetch memberships for `user_id` across `community_ids` in one query."""
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
        """Return `display_name` strictly for members with `public_display_consent=True`."""
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
        """Create and flush a neighborhood clean-air challenge initiative."""
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
        """Fetch an initiative by ID or raise `ResourceNotFoundError`."""
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
        """List initiatives filtered by community, city, and moderation visibility."""
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
        """Record a self-reported voluntary clean-air participation entry."""
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
        """Aggregate approved participation entries, action count, and estimated CO2e."""
        row = (
            await self._session.execute(
                select(
                    func.count(CommunityParticipation.id),
                    func.coalesce(func.sum(CommunityParticipation.self_reported_actions_count), 0),
                    func.coalesce(func.sum(CommunityParticipation.estimated_avoided_co2e_kg), 0.0),
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
        """Batch-aggregate participation metrics across multiple initiatives in one query."""
        if not initiative_ids:
            return {}
        rows = (
            await self._session.execute(
                select(
                    CommunityParticipation.initiative_id,
                    func.count(CommunityParticipation.id),
                    func.coalesce(func.sum(CommunityParticipation.self_reported_actions_count), 0),
                    func.coalesce(func.sum(CommunityParticipation.estimated_avoided_co2e_kg), 0.0),
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

    async def aggregate_community_metrics(self, community_id: uuid.UUID) -> tuple[int, float]:
        """Aggregate total approved actions and estimated CO2e across a community."""
        row = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(CommunityParticipation.self_reported_actions_count), 0),
                    func.coalesce(func.sum(CommunityParticipation.estimated_avoided_co2e_kg), 0.0),
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
        """Create an abuse or privacy moderation report for moderator review."""
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

    async def list_abuse_reports(self, *, status: str | None = None) -> list[CommunityAbuseReport]:
        """List moderation reports ordered by creation timestamp descending."""
        stmt = select(CommunityAbuseReport).order_by(CommunityAbuseReport.created_at.desc())
        if status is not None:
            stmt = stmt.where(CommunityAbuseReport.status == status)
        rows = await self._session.scalars(stmt.limit(200))
        return list(rows.all())

    async def require_abuse_report(self, report_id: uuid.UUID) -> CommunityAbuseReport:
        """Fetch a moderation report by ID or raise `ResourceNotFoundError`."""
        report = await self._session.scalar(
            select(CommunityAbuseReport).where(CommunityAbuseReport.id == report_id)
        )
        if report is None:
            raise ResourceNotFoundError("Moderation report was not found.")
        return report
