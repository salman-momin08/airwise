from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    AuthenticatedPrincipal,
    RequestPrincipal,
    enforce_csrf_protection,
    get_app_settings,
    get_client_ip,
    get_current_principal,
    get_response_meta,
    require_authenticated_user,
    require_moderator_or_admin,
)
from app.core.config import Settings
from app.core.rate_limit import rate_limiter
from app.db.session import get_db_session
from app.schemas.common import ApiResponse, ResponseMeta
from app.schemas.community import (
    AbuseReportSchema,
    CommunityDetailSchema,
    CommunityInitiativeSchema,
    CommunitySummarySchema,
    CreateAbuseReportRequest,
    CreateCommunityRequest,
    CreateInitiativeRequest,
    JoinCommunityRequest,
    LogParticipationRequest,
    ParticipationReceiptSchema,
)
from app.services.community.community_service import CommunityService

router = APIRouter(prefix="/communities", tags=["community"])

Database = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
Meta = Annotated[ResponseMeta, Depends(get_response_meta)]
Principal = Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)]
ModeratorPrincipal = Annotated[AuthenticatedPrincipal, Depends(require_moderator_or_admin)]
OptionalPrincipal = Annotated[RequestPrincipal, Depends(get_current_principal)]

@router.get("", response_model=ApiResponse[list[CommunitySummarySchema]])
async def list_communities(
    db: Database,
    settings: AppSettings,
    meta: Meta,
    principal: OptionalPrincipal,
    city: Annotated[str | None, Query(min_length=2, max_length=100)] = None,
) -> ApiResponse[list[CommunitySummarySchema]]:
    service = CommunityService(session=db, settings=settings)
    items = await service.list_communities(
        city=city, current_user_id=principal.user_id
    )
    return ApiResponse(data=items, meta=meta)

@router.post(
    "",
    status_code=201,
    response_model=ApiResponse[CommunityDetailSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def create_community(
    payload: CreateCommunityRequest,
    request: Request,
    principal: ModeratorPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[CommunityDetailSchema]:
    service = CommunityService(session=db, settings=settings)
    created = await service.create_community(
        actor_user_id=principal.user_id,
        payload=payload,
        client_ip=get_client_ip(request),
    )
    return ApiResponse(data=created, meta=meta)

@router.get("/{community_id}", response_model=ApiResponse[CommunityDetailSchema])
async def get_community_detail(
    community_id: uuid.UUID,
    db: Database,
    settings: AppSettings,
    meta: Meta,
    principal: OptionalPrincipal,
) -> ApiResponse[CommunityDetailSchema]:
    service = CommunityService(session=db, settings=settings)
    detail = await service.get_community_detail(
        community_id=community_id, current_user_id=principal.user_id
    )
    return ApiResponse(data=detail, meta=meta)

@router.post(
    "/{community_id}/join",
    response_model=ApiResponse[CommunityDetailSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def join_community(
    community_id: uuid.UUID,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
    payload: JoinCommunityRequest | None = None,
) -> ApiResponse[CommunityDetailSchema]:
    await rate_limiter.check("community_join", str(principal.user_id), 20, 60)
    service = CommunityService(session=db, settings=settings)
    updated = await service.join_community(
        user_id=principal.user_id,
        community_id=community_id,
        payload=payload or JoinCommunityRequest(),
    )
    return ApiResponse(data=updated, meta=meta)

@router.post(
    "/{community_id}/leave",
    response_model=ApiResponse[dict[str, str]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def leave_community(
    community_id: uuid.UUID,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[dict[str, str]]:
    service = CommunityService(session=db, settings=settings)
    res = await service.leave_community(
        user_id=principal.user_id, community_id=community_id
    )
    return ApiResponse(data=res, meta=meta)

@router.get(
    "/{community_id}/initiatives",
    response_model=ApiResponse[list[CommunityInitiativeSchema]],
)
async def list_community_initiatives(
    community_id: uuid.UUID,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[list[CommunityInitiativeSchema]]:
    service = CommunityService(session=db, settings=settings)
    items = await service.list_community_initiatives(
        community_id=community_id, include_non_active=False
    )
    return ApiResponse(data=items, meta=meta)

@router.post(
    "/{community_id}/initiatives",
    status_code=201,
    response_model=ApiResponse[CommunityInitiativeSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def create_community_initiative(
    community_id: uuid.UUID,
    payload: CreateInitiativeRequest,
    request: Request,
    principal: ModeratorPrincipal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[CommunityInitiativeSchema]:
    service = CommunityService(session=db, settings=settings)
    item = await service.create_initiative(
        actor_user_id=principal.user_id,
        community_id=community_id,
        payload=payload,
        client_ip=get_client_ip(request),
    )
    return ApiResponse(data=item, meta=meta)

@router.post(
    "/{community_id}/initiatives/{initiative_id}/participate",
    status_code=201,
    response_model=ApiResponse[ParticipationReceiptSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def log_community_participation(
    community_id: uuid.UUID,
    initiative_id: uuid.UUID,
    payload: LogParticipationRequest,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[ParticipationReceiptSchema]:
    await rate_limiter.check("community_participate", str(principal.user_id), 25, 60)
    service = CommunityService(session=db, settings=settings)
    receipt = await service.log_participation(
        user_id=principal.user_id,
        community_id=community_id,
        initiative_id=initiative_id,
        payload=payload,
    )
    return ApiResponse(data=receipt, meta=meta)

@router.post(
    "/{community_id}/reports",
    status_code=201,
    response_model=ApiResponse[AbuseReportSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def submit_community_abuse_report(
    community_id: uuid.UUID,
    payload: CreateAbuseReportRequest,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[AbuseReportSchema]:
    await rate_limiter.check("community_report", str(principal.user_id), 10, 60)
    service = CommunityService(session=db, settings=settings)
    report = await service.report_abuse(
        user_id=principal.user_id, community_id=community_id, payload=payload
    )
    return ApiResponse(data=report, meta=meta)
