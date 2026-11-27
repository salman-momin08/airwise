from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    AuthenticatedPrincipal,
    enforce_csrf_protection,
    get_app_settings,
    get_response_meta,
    require_authenticated_user,
)
from app.core.config import Settings
from app.core.rate_limit import rate_limiter
from app.db.session import get_db_session
from app.schemas.alerts import (
    AlertEvaluationSummarySchema,
    AlertRuleSchema,
    CreateAlertRuleRequest,
    NotificationSchema,
    UpdateAlertRuleRequest,
)
from app.schemas.common import ApiResponse, ResponseMeta
from app.services.alerts.alert_service import SmartAlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])
notifications_router = APIRouter(prefix="/notifications", tags=["alerts"])

Principal = Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)]
Database = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
Meta = Annotated[ResponseMeta, Depends(get_response_meta)]

@router.get("", response_model=ApiResponse[list[AlertRuleSchema]])
async def list_alert_rules(
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[list[AlertRuleSchema]]:
    service = SmartAlertService(session=db, settings=settings)
    rules = await service.list_rules(user_id=principal.user_id)
    return ApiResponse(data=rules, meta=meta)

@router.post(
    "",
    status_code=201,
    response_model=ApiResponse[AlertRuleSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def create_alert_rule(
    payload: CreateAlertRuleRequest,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[AlertRuleSchema]:
    await rate_limiter.check("alerts_mutate", str(principal.user_id), 20, 60)
    service = SmartAlertService(session=db, settings=settings)
    rule = await service.create_rule(user_id=principal.user_id, payload=payload)
    return ApiResponse(data=rule, meta=meta)

@router.patch(
    "/{rule_id}",
    response_model=ApiResponse[AlertRuleSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def update_alert_rule(
    rule_id: uuid.UUID,
    payload: UpdateAlertRuleRequest,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[AlertRuleSchema]:
    service = SmartAlertService(session=db, settings=settings)
    rule = await service.update_rule(
        user_id=principal.user_id, rule_id=rule_id, payload=payload
    )
    return ApiResponse(data=rule, meta=meta)

@router.delete(
    "/{rule_id}",
    response_model=ApiResponse[dict[str, str]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def delete_alert_rule(
    rule_id: uuid.UUID,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[dict[str, str]]:
    service = SmartAlertService(session=db, settings=settings)
    await service.delete_rule(user_id=principal.user_id, rule_id=rule_id)
    return ApiResponse(data={"status": "deleted"}, meta=meta)

@router.post(
    "/evaluate",
    response_model=ApiResponse[AlertEvaluationSummarySchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def evaluate_my_alert_rules(
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[AlertEvaluationSummarySchema]:
    await rate_limiter.check("alerts_evaluate", str(principal.user_id), 15, 60)
    service = SmartAlertService(session=db, settings=settings)
    summary = await service.evaluate_active_rules(user_id=principal.user_id)
    return ApiResponse(data=summary, meta=meta)

@router.post(
    "/unsubscribe-all",
    response_model=ApiResponse[dict[str, int]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def unsubscribe_all_alert_rules(
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[dict[str, int]]:
    service = SmartAlertService(session=db, settings=settings)
    disabled_count = await service.unsubscribe_all(user_id=principal.user_id)
    return ApiResponse(data={"disabled_rules_count": disabled_count}, meta=meta)

@notifications_router.get("", response_model=ApiResponse[list[NotificationSchema]])
async def list_notifications(
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[NotificationSchema]]:
    service = SmartAlertService(session=db, settings=settings)
    items = await service.list_notifications(user_id=principal.user_id, limit=limit)
    return ApiResponse(data=items, meta=meta)

@notifications_router.patch(
    "/{notification_id}/read",
    response_model=ApiResponse[NotificationSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[NotificationSchema]:
    service = SmartAlertService(session=db, settings=settings)
    item = await service.mark_read(
        user_id=principal.user_id, notification_id=notification_id
    )
    return ApiResponse(data=item, meta=meta)

@notifications_router.post(
    "/read-all",
    response_model=ApiResponse[dict[str, int]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def mark_all_notifications_read(
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[dict[str, int]]:
    service = SmartAlertService(session=db, settings=settings)
    marked_count = await service.mark_all_read(user_id=principal.user_id)
    return ApiResponse(data={"marked_read_count": marked_count}, meta=meta)
