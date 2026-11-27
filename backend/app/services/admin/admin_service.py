"""Platform governance service for RBAC user management, data sources, and redacted audit logs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.exceptions import ConflictError, ResourceNotFoundError
from app.core.logging import redact_sensitive_mapping
from app.core.security import hash_ip_address
from app.core.telemetry import telemetry_registry
from app.models.assistant import (
    AIGenerationMetadata,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestionJob,
)
from app.models.community_alerts import CommunityAbuseReport
from app.models.identity import AuditLog, SystemSetting, User
from app.models.telemetry import AirQualitySource
from app.repositories.identity_repository import IdentityRepository
from app.schemas.admin import (
    AdminAIMonitoringSchema,
    AdminAuditLogItemSchema,
    AdminDataSourceItemSchema,
    AdminIngestionJobItemSchema,
    AdminKnowledgeDocumentItemSchema,
    AdminKnowledgeGovernanceSchema,
    AdminOverviewSchema,
    AdminUpdateDataSourceRequest,
    AdminUpdateUserRequest,
    AdminUserItemSchema,
    SystemSettingItemSchema,
    UpsertSystemSettingRequest,
)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


DEFAULT_SOURCE_CATALOG: tuple[dict[str, object], ...] = (
    {
        "slug": "openaq-v3",
        "name": "OpenAQ Global Station Feed (v3)",
        "provider_type": "openaq",
        "license_note": "OpenAQ Open Data Attribution",
        "refresh_interval_seconds": 900,
        "priority_rank": 1,
    },
    {
        "slug": "openweather-air-pollution",
        "name": "OpenWeather Regional Air Pollution Model",
        "provider_type": "openweather",
        "license_note": "OpenWeather API Terms (Regional Model Fallback)",
        "refresh_interval_seconds": 900,
        "priority_rank": 2,
    },
    {
        "slug": "cpcb-india-reference",
        "name": "CPCB / National Air Quality Monitoring Network",
        "provider_type": "cpcb",
        "license_note": "Central Pollution Control Board Public Data",
        "refresh_interval_seconds": 900,
        "priority_rank": 1,
    },
)


class AdminGovernanceService:
    """Backend-enforced administrative governance with append-only redacted audit logs."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._identity_repo = IdentityRepository(session)

    async def get_overview(self) -> AdminOverviewSchema:
        active_users = int(
            await self._session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.deleted_at.is_(None), User.is_active.is_(True))
            )
            or 0
        )
        enabled_sources = int(
            await self._session.scalar(
                select(func.count())
                .select_from(AirQualitySource)
                .where(AirQualitySource.is_enabled.is_(True))
            )
            or 0
        )
        docs_count = int(
            await self._session.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0
        )
        chunks_count = int(
            await self._session.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0
        )
        total_ai = int(
            await self._session.scalar(select(func.count()).select_from(AIGenerationMetadata)) or 0
        )
        fallback_ai = int(
            await self._session.scalar(
                select(func.count())
                .select_from(AIGenerationMetadata)
                .where(AIGenerationMetadata.fallback_reason.is_not(None))
            )
            or 0
        )
        open_reports = int(
            await self._session.scalar(
                select(func.count())
                .select_from(CommunityAbuseReport)
                .where(CommunityAbuseReport.status == "open")
            )
            or 0
        )
        audit_count = int(
            await self._session.scalar(select(func.count()).select_from(AuditLog)) or 0
        )

        return AdminOverviewSchema(
            active_users_count=active_users,
            enabled_data_sources_count=enabled_sources,
            ingested_documents_count=docs_count,
            knowledge_chunks_count=chunks_count,
            total_ai_generations=total_ai,
            ai_fallback_rate=round(fallback_ai / total_ai, 4) if total_ai > 0 else 0.0,
            open_moderation_reports_count=open_reports,
            audit_log_entries_count=audit_count,
            active_aqi_provider_mode=self._settings.air_quality_provider,
            active_llm_provider=self._settings.llm_provider,
        )

    async def list_users(self, *, limit: int = 100) -> list[AdminUserItemSchema]:
        rows = await self._session.scalars(
            select(User)
            .options(selectinload(User.profile))
            .where(User.deleted_at.is_(None))
            .order_by(User.created_at.desc())
            .limit(limit)
        )
        items: list[AdminUserItemSchema] = []
        for user in rows:
            display = (
                user.profile.display_name if user.profile is not None else user.email.split("@")[0]
            )
            items.append(
                AdminUserItemSchema(
                    id=user.id,
                    email=user.email,
                    display_name=display,
                    role=user.role,
                    is_active=user.is_active,
                    is_email_verified=user.is_email_verified,
                    created_at=_ensure_utc(user.created_at),
                )
            )
        return items

    async def update_user_governance(
        self,
        *,
        actor_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        payload: AdminUpdateUserRequest,
        client_ip: str | None,
    ) -> AdminUserItemSchema:
        target = await self._identity_repo.get_user_by_id(target_user_id)
        if target is None:
            raise ResourceNotFoundError("Target user account was not found.")

        if target.id == actor_user_id:
            if payload.is_active is False:
                raise ConflictError("Administrators cannot deactivate their own active account.")
            if payload.role is not None and payload.role != "admin":
                raise ConflictError("Administrators cannot demote their own active account.")

        changes: dict[str, object] = {}
        if payload.role is not None and payload.role != target.role:
            changes["previous_role"] = target.role
            changes["new_role"] = payload.role
            target.role = payload.role

        if payload.is_active is not None and payload.is_active != target.is_active:
            changes["is_active"] = payload.is_active
            target.is_active = payload.is_active
            if not payload.is_active:
                await self._identity_repo.revoke_all_sessions_for_user(user_id=target.id)

        target.updated_at = datetime.now(tz=UTC)
        await self._identity_repo.append_audit_log(
            actor_user_id=actor_user_id,
            action="admin.user_updated",
            target_type="user",
            target_id=str(target.id),
            metadata_redacted=changes,
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()

        display = (
            target.profile.display_name
            if target.profile is not None
            else target.email.split("@")[0]
        )
        return AdminUserItemSchema(
            id=target.id,
            email=target.email,
            display_name=display,
            role=target.role,
            is_active=target.is_active,
            is_email_verified=target.is_email_verified,
            created_at=_ensure_utc(target.created_at),
        )

    async def list_data_sources(self) -> list[AdminDataSourceItemSchema]:
        rows = list(
            await self._session.scalars(
                select(AirQualitySource).order_by(
                    AirQualitySource.priority_rank.asc(), AirQualitySource.slug.asc()
                )
            )
        )
        return [
            AdminDataSourceItemSchema(
                id=src.id,
                slug=src.slug,
                name=src.name,
                provider_type=src.provider_type,
                license_note=src.license_note,
                refresh_interval_seconds=src.refresh_interval_seconds,
                is_enabled=src.is_enabled,
                priority_rank=src.priority_rank,
            )
            for src in rows
        ]

    async def seed_default_data_sources(
        self, *, actor_user_id: uuid.UUID, client_ip: str | None
    ) -> list[AdminDataSourceItemSchema]:
        seeded = 0
        for spec in DEFAULT_SOURCE_CATALOG:
            existing = await self._session.scalar(
                select(AirQualitySource).where(AirQualitySource.slug == str(spec["slug"]))
            )
            if existing is None:
                self._session.add(
                    AirQualitySource(
                        id=uuid.uuid4(),
                        slug=str(spec["slug"]),
                        name=str(spec["name"]),
                        provider_type=str(spec["provider_type"]),
                        license_note=str(spec["license_note"]),
                        refresh_interval_seconds=int(str(spec["refresh_interval_seconds"])),
                        is_enabled=True,
                        priority_rank=int(str(spec["priority_rank"])),
                    )
                )
                seeded += 1

        await self._identity_repo.append_audit_log(
            actor_user_id=actor_user_id,
            action="admin.data_sources_seeded",
            target_type="air_quality_source",
            target_id="catalog",
            metadata_redacted={"seeded_count": seeded},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
        return await self.list_data_sources()

    async def update_data_source(
        self,
        *,
        actor_user_id: uuid.UUID,
        source_id: uuid.UUID,
        payload: AdminUpdateDataSourceRequest,
        client_ip: str | None,
    ) -> AdminDataSourceItemSchema:
        src = await self._session.scalar(
            select(AirQualitySource).where(AirQualitySource.id == source_id)
        )
        if src is None:
            raise ResourceNotFoundError("Air quality data source was not found.")

        changes: dict[str, object] = {}
        if payload.is_enabled is not None:
            src.is_enabled = payload.is_enabled
            changes["is_enabled"] = payload.is_enabled
        if payload.priority_rank is not None:
            src.priority_rank = payload.priority_rank
            changes["priority_rank"] = payload.priority_rank
        if payload.refresh_interval_seconds is not None:
            src.refresh_interval_seconds = payload.refresh_interval_seconds
            changes["refresh_interval_seconds"] = payload.refresh_interval_seconds

        await self._identity_repo.append_audit_log(
            actor_user_id=actor_user_id,
            action="admin.data_source_updated",
            target_type="air_quality_source",
            target_id=str(src.id),
            metadata_redacted=changes,
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
        return AdminDataSourceItemSchema(
            id=src.id,
            slug=src.slug,
            name=src.name,
            provider_type=src.provider_type,
            license_note=src.license_note,
            refresh_interval_seconds=src.refresh_interval_seconds,
            is_enabled=src.is_enabled,
            priority_rank=src.priority_rank,
        )

    async def get_knowledge_governance(self) -> AdminKnowledgeGovernanceSchema:
        docs = list(
            await self._session.scalars(
                select(KnowledgeDocument).order_by(KnowledgeDocument.last_reviewed_date.desc())
            )
        )
        chunk_counts_rows = await self._session.execute(
            select(KnowledgeChunk.document_id, func.count(KnowledgeChunk.id)).group_by(
                KnowledgeChunk.document_id
            )
        )
        chunk_counts: dict[uuid.UUID, int] = {doc_id: int(cnt) for doc_id, cnt in chunk_counts_rows}
        horizon_cutoff = datetime.now(tz=UTC) - timedelta(days=730)

        doc_items = [
            AdminKnowledgeDocumentItemSchema(
                id=d.id,
                title=d.title,
                publisher=d.publisher,
                source_url=d.source_url,
                jurisdiction=d.jurisdiction,
                trust_classification=d.trust_classification,
                publication_date=(_ensure_utc(d.publication_date) if d.publication_date else None),
                last_reviewed_date=_ensure_utc(d.last_reviewed_date),
                chunks_count=chunk_counts.get(d.id, 0),
                is_review_overdue=_ensure_utc(d.last_reviewed_date) < horizon_cutoff,
            )
            for d in docs
        ]

        jobs = list(
            await self._session.scalars(
                select(KnowledgeIngestionJob)
                .order_by(KnowledgeIngestionJob.created_at.desc())
                .limit(50)
            )
        )
        job_items = [
            AdminIngestionJobItemSchema(
                id=j.id,
                source_url=j.source_url,
                status=j.status,
                error_code=j.error_code,
                created_at=_ensure_utc(j.created_at),
                completed_at=_ensure_utc(j.completed_at) if j.completed_at else None,
            )
            for j in jobs
        ]
        return AdminKnowledgeGovernanceSchema(documents=doc_items, recent_jobs=job_items)

    async def get_ai_monitoring(self) -> AdminAIMonitoringSchema:
        rows = list(
            await self._session.scalars(
                select(AIGenerationMetadata)
                .order_by(AIGenerationMetadata.created_at.desc())
                .limit(1000)
            )
        )
        total = len(rows)
        fallbacks = 0
        total_tokens = 0
        latencies: list[int] = []
        reasons: dict[str, int] = {}
        tools_map: dict[str, int] = {}

        for row in rows:
            total_tokens += row.token_usage
            latencies.append(row.latency_ms)
            if row.fallback_reason:
                fallbacks += 1
                reasons[row.fallback_reason] = reasons.get(row.fallback_reason, 0) + 1
            for tool_name in row.tools_invoked:
                tools_map[tool_name] = tools_map.get(tool_name, 0) + 1

        avg_lat = round(sum(latencies) / total, 2) if total > 0 else 0.0
        p95_lat = 0.0
        if latencies:
            sorted_lat = sorted(latencies)
            idx = min(len(sorted_lat) - 1, max(0, round(0.95 * (len(sorted_lat) - 1))))
            p95_lat = float(sorted_lat[idx])

        return AdminAIMonitoringSchema(
            total_generations=total,
            fallback_generations=fallbacks,
            fallback_rate=round(fallbacks / total, 4) if total > 0 else 0.0,
            total_tokens=total_tokens,
            avg_latency_ms=avg_lat,
            p95_latency_ms=p95_lat,
            fallback_reasons=reasons,
            tool_invocations=tools_map,
            runtime_http_p95_ms=telemetry_registry.percentile_latency_ms(95.0),
            runtime_aqi_cache_hits=telemetry_registry.aqi_cache_hits_total,
            runtime_aqi_cache_misses=telemetry_registry.aqi_cache_misses_total,
        )

    async def list_audit_logs(
        self, *, action_prefix: str | None = None, limit: int = 100
    ) -> list[AdminAuditLogItemSchema]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        if action_prefix:
            stmt = stmt.where(AuditLog.action.startswith(action_prefix.strip()))
        rows = await self._session.scalars(stmt)
        return [
            AdminAuditLogItemSchema(
                id=log.id,
                actor_user_id=str(log.actor_user_id) if log.actor_user_id else None,
                action=log.action,
                target_type=log.target_type,
                target_id=log.target_id,
                metadata_redacted=redact_sensitive_mapping(dict(log.metadata_redacted)),
                created_at=_ensure_utc(log.created_at),
            )
            for log in rows
        ]

    async def list_system_settings(self) -> list[SystemSettingItemSchema]:
        rows = await self._session.scalars(select(SystemSetting).order_by(SystemSetting.key.asc()))
        return [
            SystemSettingItemSchema(
                key=item.key,
                value=redact_sensitive_mapping(dict(item.value)),
                updated_by=str(item.updated_by) if item.updated_by else None,
                updated_at=_ensure_utc(item.updated_at),
            )
            for item in rows
        ]

    async def upsert_system_setting(
        self,
        *,
        actor_user_id: uuid.UUID,
        key: str,
        payload: UpsertSystemSettingRequest,
        client_ip: str | None,
    ) -> SystemSettingItemSchema:
        now = datetime.now(tz=UTC)
        clean_value = redact_sensitive_mapping(dict(payload.value))
        setting = await self._session.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if setting is None:
            setting = SystemSetting(
                key=key,
                value=clean_value,
                updated_by=actor_user_id,
                updated_at=now,
            )
            self._session.add(setting)
        else:
            setting.value = clean_value
            setting.updated_by = actor_user_id
            setting.updated_at = now

        await self._identity_repo.append_audit_log(
            actor_user_id=actor_user_id,
            action="admin.system_setting_updated",
            target_type="system_setting",
            target_id=key,
            metadata_redacted={"keys_updated": sorted(clean_value.keys())},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
        return SystemSettingItemSchema(
            key=setting.key,
            value=setting.value,
            updated_by=str(setting.updated_by) if setting.updated_by else None,
            updated_at=_ensure_utc(setting.updated_at),
        )
