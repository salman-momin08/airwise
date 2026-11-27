"""Admin governance endpoints for users, data sources, RAG, AI metrics, and audit logs."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    AuthenticatedPrincipal,
    enforce_csrf_protection,
    get_app_settings,
    get_client_ip,
    get_response_meta,
    require_admin_user,
    require_moderator_or_admin,
)
from app.core.config import Settings
from app.db.session import get_db_session
from app.schemas.admin import (
    AdminAIMonitoringSchema,
    AdminAuditLogItemSchema,
    AdminDataSourceItemSchema,
    AdminKnowledgeGovernanceSchema,
    AdminOverviewSchema,
    AdminUpdateDataSourceRequest,
    AdminUpdateUserRequest,
    AdminUserItemSchema,
    SystemSettingItemSchema,
    UpsertSystemSettingRequest,
)
from app.schemas.common import ApiResponse, ResponseMeta
from app.schemas.community import (
    AbuseReportSchema,
    CommunityInitiativeSchema,
    ModerateInitiativeRequest,
    ResolveAbuseReportRequest,
)
from app.services.admin.admin_service import AdminGovernanceService
from app.services.community.community_service import CommunityService

router = APIRouter(prefix="/admin", tags=["admin"])

Database = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
Meta = Annotated[ResponseMeta, Depends(get_response_meta)]
AdminPrincipal = Annotated[AuthenticatedPrincipal, Depends(require_admin_user)]
ModeratorPrincipal = Annotated[AuthenticatedPrincipal, Depends(require_moderator_or_admin)]


@router.get("/status", response_model=ApiResponse[dict[str, str]])
async def get_admin_status(
    principal: AdminPrincipal,
    meta: Meta,
) -> ApiResponse[dict[str, str]]:
    return ApiResponse(
        data={"admin_user_id": str(principal.user_id), "status": "authorized"},
        meta=meta,
    )


@router.get("/overview", response_model=ApiResponse[AdminOverviewSchema])
async def get_admin_overview(
    _principal: AdminPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[AdminOverviewSchema]:
    service = AdminGovernanceService(session=db, settings=settings)
    overview = await service.get_overview()
    return ApiResponse(data=overview, meta=meta)


@router.get("/users", response_model=ApiResponse[list[AdminUserItemSchema]])
async def list_admin_users(
    _principal: AdminPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ApiResponse[list[AdminUserItemSchema]]:
    service = AdminGovernanceService(session=db, settings=settings)
    users = await service.list_users(limit=limit)
    return ApiResponse(data=users, meta=meta)


@router.patch(
    "/users/{user_id}",
    response_model=ApiResponse[AdminUserItemSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def update_admin_user_governance(
    user_id: uuid.UUID,
    payload: AdminUpdateUserRequest,
    request: Request,
    principal: AdminPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[AdminUserItemSchema]:
    service = AdminGovernanceService(session=db, settings=settings)
    updated = await service.update_user_governance(
        actor_user_id=principal.user_id,
        target_user_id=user_id,
        payload=payload,
        client_ip=get_client_ip(request),
    )
    return ApiResponse(data=updated, meta=meta)


@router.get("/data-sources", response_model=ApiResponse[list[AdminDataSourceItemSchema]])
async def list_admin_data_sources(
    _principal: AdminPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[list[AdminDataSourceItemSchema]]:
    service = AdminGovernanceService(session=db, settings=settings)
    sources = await service.list_data_sources()
    return ApiResponse(data=sources, meta=meta)


@router.post(
    "/data-sources/seed-defaults",
    response_model=ApiResponse[list[AdminDataSourceItemSchema]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def seed_admin_default_data_sources(
    request: Request,
    principal: AdminPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[list[AdminDataSourceItemSchema]]:
    service = AdminGovernanceService(session=db, settings=settings)
    sources = await service.seed_default_data_sources(
        actor_user_id=principal.user_id, client_ip=get_client_ip(request)
    )
    return ApiResponse(data=sources, meta=meta)


@router.patch(
    "/data-sources/{source_id}",
    response_model=ApiResponse[AdminDataSourceItemSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def update_admin_data_source(
    source_id: uuid.UUID,
    payload: AdminUpdateDataSourceRequest,
    request: Request,
    principal: AdminPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[AdminDataSourceItemSchema]:
    service = AdminGovernanceService(session=db, settings=settings)
    updated = await service.update_data_source(
        actor_user_id=principal.user_id,
        source_id=source_id,
        payload=payload,
        client_ip=get_client_ip(request),
    )
    return ApiResponse(data=updated, meta=meta)


@router.get("/knowledge-base", response_model=ApiResponse[AdminKnowledgeGovernanceSchema])
async def get_admin_knowledge_governance(
    _principal: AdminPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[AdminKnowledgeGovernanceSchema]:
    service = AdminGovernanceService(session=db, settings=settings)
    governance = await service.get_knowledge_governance()
    return ApiResponse(data=governance, meta=meta)


@router.get("/ai-monitoring", response_model=ApiResponse[AdminAIMonitoringSchema])
async def get_admin_ai_monitoring(
    _principal: AdminPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[AdminAIMonitoringSchema]:
    service = AdminGovernanceService(session=db, settings=settings)
    telemetry = await service.get_ai_monitoring()
    return ApiResponse(data=telemetry, meta=meta)


@router.get("/audit-logs", response_model=ApiResponse[list[AdminAuditLogItemSchema]])
async def list_admin_audit_logs(
    _principal: AdminPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
    action_prefix: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ApiResponse[list[AdminAuditLogItemSchema]]:
    service = AdminGovernanceService(session=db, settings=settings)
    logs = await service.list_audit_logs(action_prefix=action_prefix, limit=limit)
    return ApiResponse(data=logs, meta=meta)


@router.get("/settings", response_model=ApiResponse[list[SystemSettingItemSchema]])
async def list_admin_system_settings(
    _principal: AdminPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[list[SystemSettingItemSchema]]:
    service = AdminGovernanceService(session=db, settings=settings)
    items = await service.list_system_settings()
    return ApiResponse(data=items, meta=meta)


@router.put(
    "/settings/{key}",
    response_model=ApiResponse[SystemSettingItemSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def upsert_admin_system_setting(
    key: str,
    payload: UpsertSystemSettingRequest,
    request: Request,
    principal: AdminPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[SystemSettingItemSchema]:
    service = AdminGovernanceService(session=db, settings=settings)
    item = await service.upsert_system_setting(
        actor_user_id=principal.user_id,
        key=key,
        payload=payload,
        client_ip=get_client_ip(request),
    )
    return ApiResponse(data=item, meta=meta)


@router.get(
    "/community/reports",
    response_model=ApiResponse[list[AbuseReportSchema]],
)
async def list_community_moderation_reports(
    _principal: ModeratorPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
    status: Annotated[str | None, Query(pattern=r"^(open|resolved_removed|dismissed)$")] = None,
) -> ApiResponse[list[AbuseReportSchema]]:
    service = CommunityService(session=db, settings=settings)
    reports = await service.list_moderation_reports(status=status)
    return ApiResponse(data=reports, meta=meta)


@router.patch(
    "/community/reports/{report_id}",
    response_model=ApiResponse[AbuseReportSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def resolve_community_moderation_report(
    report_id: uuid.UUID,
    payload: ResolveAbuseReportRequest,
    request: Request,
    principal: ModeratorPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[AbuseReportSchema]:
    service = CommunityService(session=db, settings=settings)
    resolved = await service.resolve_moderation_report(
        actor_user_id=principal.user_id,
        report_id=report_id,
        payload=payload,
        client_ip=get_client_ip(request),
    )
    return ApiResponse(data=resolved, meta=meta)


@router.patch(
    "/community/initiatives/{initiative_id}",
    response_model=ApiResponse[CommunityInitiativeSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def moderate_community_initiative(
    initiative_id: uuid.UUID,
    payload: ModerateInitiativeRequest,
    request: Request,
    principal: ModeratorPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[CommunityInitiativeSchema]:
    service = CommunityService(session=db, settings=settings)
    moderated = await service.moderate_initiative(
        actor_user_id=principal.user_id,
        initiative_id=initiative_id,
        payload=payload,
        client_ip=get_client_ip(request),
    )
    return ApiResponse(data=moderated, meta=meta)
