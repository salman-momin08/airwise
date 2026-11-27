"""Neighborhood community groups, voluntary clean-air challenges, and abuse moderation service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.core.security import hash_ip_address
from app.models.community_alerts import Community, CommunityInitiative
from app.repositories.alerts_community_repository import AlertsCommunityRepository
from app.repositories.identity_repository import IdentityRepository
from app.schemas.community import (
    AbuseReportSchema,
    ChallengeTypeLiteral,
    CommunityDetailSchema,
    CommunityInitiativeSchema,
    CommunitySummarySchema,
    CreateAbuseReportRequest,
    CreateCommunityRequest,
    CreateInitiativeRequest,
    JoinCommunityRequest,
    LogParticipationRequest,
    ModerateInitiativeRequest,
    ModerationStatusLiteral,
    ParticipationReceiptSchema,
    ReportReasonLiteral,
    ReportResolutionStatusLiteral,
    ResolveAbuseReportRequest,
)
from app.schemas.impact import TransportImpactRequest
from app.services.air_quality.aqi_calculator import AQIStandard
from app.services.impact.impact_service import ImpactEngineService


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class CommunityService:
    """Service enforcing coarse neighborhood privacy, opt-in display consent, and moderation."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = AlertsCommunityRepository(session)
        self._identity_repo = IdentityRepository(session)
        self._impact_service = ImpactEngineService(session, settings)

    async def _build_summary(
        self, comm: Community, *, current_user_id: uuid.UUID | None
    ) -> CommunitySummarySchema:
        member_count = await self._repo.count_members(comm.id)
        active_inits = await self._repo.list_initiatives(
            community_id=comm.id, include_non_active=False
        )
        membership = (
            await self._repo.get_membership(community_id=comm.id, user_id=current_user_id)
            if current_user_id is not None
            else None
        )
        return CommunitySummarySchema(
            id=comm.id,
            slug=comm.slug,
            name=comm.name,
            city=comm.city,
            coarse_boundary_label=comm.coarse_boundary_label,
            description=comm.description,
            member_count=member_count,
            active_initiatives_count=len(active_inits),
            is_current_user_member=membership is not None,
            current_user_public_display_consent=(
                bool(membership.public_display_consent) if membership is not None else False
            ),
            created_at=_ensure_utc(comm.created_at),
        )

    def _serialize_initiative_from_metrics(
        self,
        item: CommunityInitiative,
        metrics: tuple[int, int, float],
        *,
        community_name: str | None = None,
        city: str | None = None,
    ) -> CommunityInitiativeSchema:
        entries, actions, co2e = metrics
        return CommunityInitiativeSchema(
            id=item.id,
            community_id=item.community_id,
            community_name=community_name,
            city=city,
            title=item.title,
            description=item.description,
            challenge_type=cast(ChallengeTypeLiteral, item.challenge_type),
            starts_at=_ensure_utc(item.starts_at),
            ends_at=_ensure_utc(item.ends_at),
            moderation_status=cast(ModerationStatusLiteral, item.moderation_status),
            participant_entries_count=entries,
            total_self_reported_actions=actions,
            total_estimated_avoided_co2e_kg=co2e,
            is_self_reported_aggregate=True,
            created_at=_ensure_utc(item.created_at),
        )

    async def _serialize_initiative(
        self,
        item: CommunityInitiative,
        *,
        community_name: str | None = None,
        city: str | None = None,
    ) -> CommunityInitiativeSchema:
        metrics = await self._repo.aggregate_initiative_metrics(item.id)
        return self._serialize_initiative_from_metrics(
            item, metrics, community_name=community_name, city=city
        )

    async def list_communities(
        self, *, city: str | None = None, current_user_id: uuid.UUID | None = None
    ) -> list[CommunitySummarySchema]:
        rows = await self._repo.list_communities(city=city)
        if not rows:
            return []
        comm_ids = {comm.id for comm in rows}
        member_counts = await self._repo.count_members_batch(comm_ids)
        active_init_counts = await self._repo.count_active_initiatives_batch(comm_ids)
        memberships = (
            await self._repo.get_memberships_batch(community_ids=comm_ids, user_id=current_user_id)
            if current_user_id is not None
            else {}
        )
        return [
            CommunitySummarySchema(
                id=comm.id,
                slug=comm.slug,
                name=comm.name,
                city=comm.city,
                coarse_boundary_label=comm.coarse_boundary_label,
                description=comm.description,
                member_count=member_counts.get(comm.id, 0),
                active_initiatives_count=active_init_counts.get(comm.id, 0),
                is_current_user_member=comm.id in memberships,
                current_user_public_display_consent=(
                    bool(memberships[comm.id].public_display_consent)
                    if comm.id in memberships
                    else False
                ),
                created_at=_ensure_utc(comm.created_at),
            )
            for comm in rows
        ]

    async def get_community_detail(
        self, *, community_id: uuid.UUID, current_user_id: uuid.UUID | None = None
    ) -> CommunityDetailSchema:
        comm = await self._repo.require_community(community_id)
        summary = await self._build_summary(comm, current_user_id=current_user_id)
        total_actions, total_co2e = await self._repo.aggregate_community_metrics(comm.id)
        consented_names = await self._repo.list_consented_member_names(comm.id)
        return CommunityDetailSchema(
            **summary.model_dump(),
            moderation_policy=comm.moderation_policy,
            total_self_reported_actions=total_actions,
            total_estimated_avoided_co2e_kg=total_co2e,
            consented_member_display_names=consented_names,
        )

    async def create_community(
        self,
        *,
        actor_user_id: uuid.UUID,
        payload: CreateCommunityRequest,
        client_ip: str | None,
    ) -> CommunityDetailSchema:
        comm = await self._repo.create_community(
            slug=payload.slug,
            name=payload.name,
            city=payload.city,
            coarse_boundary_label=payload.coarse_boundary_label,
            description=payload.description,
            moderation_policy=payload.moderation_policy,
            created_by=actor_user_id,
        )
        await self._repo.upsert_membership(
            community_id=comm.id,
            user_id=actor_user_id,
            public_display_consent=False,
            role="moderator",
        )
        await self._identity_repo.append_audit_log(
            actor_user_id=actor_user_id,
            action="community.created",
            target_type="community",
            target_id=str(comm.id),
            metadata_redacted={"slug": comm.slug, "city": comm.city},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
        return await self.get_community_detail(community_id=comm.id, current_user_id=actor_user_id)

    async def join_community(
        self,
        *,
        user_id: uuid.UUID,
        community_id: uuid.UUID,
        payload: JoinCommunityRequest,
    ) -> CommunityDetailSchema:
        await self._repo.require_community(community_id)
        await self._repo.upsert_membership(
            community_id=community_id,
            user_id=user_id,
            public_display_consent=payload.public_display_consent,
        )
        await self._session.commit()
        return await self.get_community_detail(community_id=community_id, current_user_id=user_id)

    async def leave_community(
        self, *, user_id: uuid.UUID, community_id: uuid.UUID
    ) -> dict[str, str]:
        await self._repo.require_community(community_id)
        await self._repo.remove_membership(community_id=community_id, user_id=user_id)
        await self._session.commit()
        return {"status": "left"}

    async def list_community_initiatives(
        self, *, community_id: uuid.UUID, include_non_active: bool = False
    ) -> list[CommunityInitiativeSchema]:
        comm = await self._repo.require_community(community_id)
        rows = await self._repo.list_initiatives(
            community_id=community_id, include_non_active=include_non_active
        )
        metrics_by_id = await self._repo.aggregate_initiatives_metrics_batch(
            {item.id for item in rows}
        )
        return [
            self._serialize_initiative_from_metrics(
                item,
                metrics_by_id.get(item.id, (0, 0, 0.0)),
                community_name=comm.name,
                city=comm.city,
            )
            for item in rows
        ]

    async def list_public_initiatives_for_ai(
        self, *, city: str | None = None
    ) -> list[CommunityInitiativeSchema]:
        communities = {c.id: c for c in await self._repo.list_communities(city=city)}
        rows = (await self._repo.list_initiatives(city=city, include_non_active=False))[:15]
        metrics_by_id = await self._repo.aggregate_initiatives_metrics_batch(
            {item.id for item in rows}
        )
        return [
            self._serialize_initiative_from_metrics(
                item,
                metrics_by_id.get(item.id, (0, 0, 0.0)),
                community_name=(
                    communities[item.community_id].name
                    if item.community_id in communities
                    else None
                ),
                city=(
                    communities[item.community_id].city
                    if item.community_id in communities
                    else city
                ),
            )
            for item in rows
        ]

    async def create_initiative(
        self,
        *,
        actor_user_id: uuid.UUID,
        community_id: uuid.UUID,
        payload: CreateInitiativeRequest,
        client_ip: str | None,
    ) -> CommunityInitiativeSchema:
        comm = await self._repo.require_community(community_id)
        starts = _ensure_utc(payload.starts_at)
        ends = _ensure_utc(payload.ends_at)
        item = await self._repo.create_initiative(
            community_id=comm.id,
            title=payload.title,
            description=payload.description,
            challenge_type=payload.challenge_type,
            starts_at=starts,
            ends_at=ends,
            created_by=actor_user_id,
        )
        await self._identity_repo.append_audit_log(
            actor_user_id=actor_user_id,
            action="community.initiative_created",
            target_type="community_initiative",
            target_id=str(item.id),
            metadata_redacted={
                "community_id": str(comm.id),
                "challenge_type": item.challenge_type,
            },
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
        return await self._serialize_initiative(item, community_name=comm.name, city=comm.city)

    async def log_participation(
        self,
        *,
        user_id: uuid.UUID,
        community_id: uuid.UUID,
        initiative_id: uuid.UUID,
        payload: LogParticipationRequest,
    ) -> ParticipationReceiptSchema:
        await self._repo.require_community(community_id)
        membership = await self._repo.get_membership(community_id=community_id, user_id=user_id)
        if membership is None:
            raise AuthorizationError(
                message="Join this neighborhood community before logging challenge actions.",
                code="COMMUNITY_MEMBERSHIP_REQUIRED",
            )
        initiative = await self._repo.require_initiative(initiative_id)
        if initiative.community_id != community_id or initiative.moderation_status != "active":
            raise AuthorizationError(
                message="This initiative is not currently accepting participation entries.",
                code="INITIATIVE_INACTIVE",
            )

        avoided_co2e = 0.0
        if payload.commute_distance_saved_km > 0:
            calc_res, _ = await self._impact_service.calculate(
                TransportImpactRequest(
                    distance_km=payload.commute_distance_saved_km,
                    baseline_mode="car_solo_petrol",
                    alternative_mode="metro_rail",
                    standard=AQIStandard.INDIA_NAQI,
                )
            )
            avoided_co2e = max(0.0, calc_res.estimated_difference)

        entry = await self._repo.log_participation(
            initiative_id=initiative.id,
            user_id=user_id,
            actions_count=payload.self_reported_actions_count,
            avoided_co2e_kg=avoided_co2e,
            note=payload.note,
        )
        await self._session.commit()
        return ParticipationReceiptSchema(
            id=entry.id,
            initiative_id=entry.initiative_id,
            self_reported_actions_count=entry.self_reported_actions_count,
            estimated_avoided_co2e_kg=entry.estimated_avoided_co2e_kg,
            is_self_reported=True,
            is_estimate=True,
            reported_at=_ensure_utc(entry.reported_at),
        )

    async def report_abuse(
        self,
        *,
        user_id: uuid.UUID,
        community_id: uuid.UUID,
        payload: CreateAbuseReportRequest,
    ) -> AbuseReportSchema:
        await self._repo.require_community(community_id)
        if payload.initiative_id is not None:
            init = await self._repo.require_initiative(payload.initiative_id)
            if init.community_id != community_id:
                raise AuthorizationError(
                    message="Initiative does not belong to the specified community.",
                    code="INVALID_INITIATIVE_COMMUNITY",
                )
        report = await self._repo.create_abuse_report(
            community_id=community_id,
            initiative_id=payload.initiative_id,
            reporter_user_id=user_id,
            reason_category=payload.reason_category,
            details=payload.details,
        )
        await self._session.commit()
        return AbuseReportSchema(
            id=report.id,
            community_id=report.community_id,
            initiative_id=report.initiative_id,
            reason_category=cast(ReportReasonLiteral, report.reason_category),
            details=report.details,
            status=cast(ReportResolutionStatusLiteral, report.status),
            resolution_note=report.resolution_note,
            created_at=_ensure_utc(report.created_at),
            resolved_at=_ensure_utc(report.resolved_at) if report.resolved_at else None,
        )

    async def list_moderation_reports(
        self, *, status: str | None = None
    ) -> list[AbuseReportSchema]:
        rows = await self._repo.list_abuse_reports(status=status)
        return [
            AbuseReportSchema(
                id=r.id,
                community_id=r.community_id,
                initiative_id=r.initiative_id,
                reason_category=cast(ReportReasonLiteral, r.reason_category),
                details=r.details,
                status=cast(ReportResolutionStatusLiteral, r.status),
                resolution_note=r.resolution_note,
                created_at=_ensure_utc(r.created_at),
                resolved_at=_ensure_utc(r.resolved_at) if r.resolved_at else None,
            )
            for r in rows
        ]

    async def resolve_moderation_report(
        self,
        *,
        actor_user_id: uuid.UUID,
        report_id: uuid.UUID,
        payload: ResolveAbuseReportRequest,
        client_ip: str | None,
    ) -> AbuseReportSchema:
        report = await self._repo.require_abuse_report(report_id)
        now = datetime.now(tz=UTC)
        if payload.action == "hide_initiative" and report.initiative_id is not None:
            init = await self._repo.require_initiative(report.initiative_id)
            init.moderation_status = "hidden"
            report.status = "resolved_removed"
        else:
            report.status = (
                "resolved_removed" if payload.action == "hide_initiative" else "dismissed"
            )
        report.resolved_by = actor_user_id
        report.resolution_note = payload.resolution_note
        report.resolved_at = now

        await self._identity_repo.append_audit_log(
            actor_user_id=actor_user_id,
            action="community.report_resolved",
            target_type="community_abuse_report",
            target_id=str(report.id),
            metadata_redacted={
                "decision": payload.action,
                "initiative_id": str(report.initiative_id) if report.initiative_id else None,
            },
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
        return AbuseReportSchema(
            id=report.id,
            community_id=report.community_id,
            initiative_id=report.initiative_id,
            reason_category=cast(ReportReasonLiteral, report.reason_category),
            details=report.details,
            status=cast(ReportResolutionStatusLiteral, report.status),
            resolution_note=report.resolution_note,
            created_at=_ensure_utc(report.created_at),
            resolved_at=_ensure_utc(report.resolved_at) if report.resolved_at else None,
        )

    async def moderate_initiative(
        self,
        *,
        actor_user_id: uuid.UUID,
        initiative_id: uuid.UUID,
        payload: ModerateInitiativeRequest,
        client_ip: str | None,
    ) -> CommunityInitiativeSchema:
        init = await self._repo.require_initiative(initiative_id)
        comm = await self._repo.require_community(init.community_id)
        init.moderation_status = payload.moderation_status
        await self._identity_repo.append_audit_log(
            actor_user_id=actor_user_id,
            action="community.initiative_moderated",
            target_type="community_initiative",
            target_id=str(init.id),
            metadata_redacted={"new_status": payload.moderation_status},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
        return await self._serialize_initiative(init, community_name=comm.name, city=comm.city)
