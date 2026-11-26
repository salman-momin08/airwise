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
from app.schemas.common import ApiResponse, ResponseMeta
from app.schemas.community import (
    AbuseReportSchema,
    CommunityInitiativeSchema,
    ModerateInitiativeRequest,
    ResolveAbuseReportRequest,
)
from app.services.community.community_service import CommunityService

router = APIRouter(prefix="/admin", tags=["admin"])

Database = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
Meta = Annotated[ResponseMeta, Depends(get_response_meta)]
ModeratorPrincipal = Annotated[AuthenticatedPrincipal, Depends(require_moderator_or_admin)]


@router.get("/status", response_model=ApiResponse[dict[str, str]])
async def get_admin_status(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_admin_user)],
    meta: Meta,
) -> ApiResponse[dict[str, str]]:
    return ApiResponse(
        data={"admin_user_id": str(principal.user_id), "status": "authorized"},
        meta=meta,
    )


@router.get(
    "/community/reports",
    response_model=ApiResponse[list[AbuseReportSchema]],
)
async def list_community_moderation_reports(
    _principal: ModeratorPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
    status: Annotated[
        str | None, Query(pattern=r"^(open|resolved_removed|dismissed)$")
    ] = None,
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
