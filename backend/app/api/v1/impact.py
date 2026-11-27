from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    AuthenticatedPrincipal,
    RequestPrincipal,
    enforce_csrf_protection,
    get_app_settings,
    get_current_principal,
    get_response_meta,
    require_authenticated_user,
)
from app.core.config import Settings
from app.core.rate_limit import rate_limiter
from app.core.security import UserRole
from app.db.session import get_db_session
from app.schemas.common import ApiResponse, ResponseMeta
from app.schemas.impact import (
    EmissionFactorSchema,
    ImpactCalculationRequest,
    ImpactEstimateSchema,
    ImpactSummarySchema,
    LoggedUserActionSchema,
    LogUserActionRequest,
)
from app.services.impact.impact_service import ImpactEngineService, serialize_impact_result

router = APIRouter(prefix="/impact", tags=["impact"])

Database = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
Meta = Annotated[ResponseMeta, Depends(get_response_meta)]
Principal = Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)]

@router.get("/factors", response_model=ApiResponse[list[EmissionFactorSchema]])
async def list_emission_factors_endpoint(
    db: Database,
    settings: AppSettings,
    meta: Meta,
    category: Annotated[str | None, Query(pattern=r"^(transport|electricity_grid|fuel)$")] = None,
) -> ApiResponse[list[EmissionFactorSchema]]:
    service = ImpactEngineService(session=db, settings=settings)
    factors = await service.list_emission_factors(category=category)
    return ApiResponse(data=factors, meta=meta)

@router.post("/calculate", response_model=ApiResponse[ImpactEstimateSchema])
async def calculate_impact_endpoint(
    payload: ImpactCalculationRequest,
    request: Request,
    db: Database,
    settings: AppSettings,
    meta: Meta,
    principal: Annotated[RequestPrincipal, Depends(get_current_principal)],
) -> ApiResponse[ImpactEstimateSchema]:
    if principal.role != UserRole.GUEST and principal.user_id is not None:
        enforce_csrf_protection(
            request=request,
            settings=settings,
            x_csrf_token=request.headers.get("X-CSRF-Token"),
        )
    service = ImpactEngineService(session=db, settings=settings)
    result, screening = await service.calculate(payload)
    return ApiResponse(
        data=serialize_impact_result(result, screening=screening),
        meta=meta,
    )

@router.post(
    "/actions",
    status_code=201,
    response_model=ApiResponse[LoggedUserActionSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def log_user_action_endpoint(
    payload: LogUserActionRequest,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[LoggedUserActionSchema]:
    await rate_limiter.check("impact_actions", str(principal.user_id), 30, 60)
    service = ImpactEngineService(session=db, settings=settings)
    logged = await service.log_user_action(user_id=principal.user_id, payload=payload)
    return ApiResponse(data=logged, meta=meta)

@router.get("/summary", response_model=ApiResponse[ImpactSummarySchema])
async def get_impact_summary_endpoint(
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[ImpactSummarySchema]:
    service = ImpactEngineService(session=db, settings=settings)
    summary = await service.get_user_summary(user_id=principal.user_id)
    return ApiResponse(data=summary, meta=meta)

@router.get("/history", response_model=ApiResponse[list[LoggedUserActionSchema]])
async def get_impact_history_endpoint(
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[LoggedUserActionSchema]]:
    service = ImpactEngineService(session=db, settings=settings)
    history = await service.get_user_history(user_id=principal.user_id, limit=limit)
    return ApiResponse(data=history, meta=meta)
