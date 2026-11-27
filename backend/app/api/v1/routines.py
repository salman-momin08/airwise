from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
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
from app.schemas.common import ApiResponse, ResponseMeta
from app.schemas.routines import (
    DailyRoutineSchema,
    GenerateRoutineRequest,
    UpdateRoutineRequest,
)
from app.services.routines.routine_service import RoutinePlannerService

router = APIRouter(prefix="/routines", tags=["routines"])

Principal = Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)]
Database = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
Meta = Annotated[ResponseMeta, Depends(get_response_meta)]

@router.post(
    "/generate",
    status_code=201,
    response_model=ApiResponse[DailyRoutineSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def generate_daily_routine(
    payload: GenerateRoutineRequest,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[DailyRoutineSchema]:
    await rate_limiter.check("routines_generate", str(principal.user_id), 20, 60)
    service = RoutinePlannerService(session=db, settings=settings)
    routine = await service.generate_draft_routine(user_id=principal.user_id, payload=payload)
    return ApiResponse(data=routine, meta=meta)

@router.get("", response_model=ApiResponse[list[DailyRoutineSchema]])
async def list_daily_routines(
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[list[DailyRoutineSchema]]:
    service = RoutinePlannerService(session=db, settings=settings)
    routines = await service.list_routines(user_id=principal.user_id)
    return ApiResponse(data=routines, meta=meta)

@router.get("/{routine_id}", response_model=ApiResponse[DailyRoutineSchema])
async def get_daily_routine(
    routine_id: uuid.UUID,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[DailyRoutineSchema]:
    service = RoutinePlannerService(session=db, settings=settings)
    routine = await service.get_routine(user_id=principal.user_id, routine_id=routine_id)
    return ApiResponse(data=routine, meta=meta)

@router.patch(
    "/{routine_id}",
    response_model=ApiResponse[DailyRoutineSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def update_daily_routine(
    routine_id: uuid.UUID,
    payload: UpdateRoutineRequest,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[DailyRoutineSchema]:
    service = RoutinePlannerService(session=db, settings=settings)
    updated = await service.update_routine(
        user_id=principal.user_id,
        routine_id=routine_id,
        payload=payload,
    )
    return ApiResponse(data=updated, meta=meta)

@router.delete(
    "/{routine_id}",
    response_model=ApiResponse[dict[str, str]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def delete_daily_routine(
    routine_id: uuid.UUID,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[dict[str, str]]:
    service = RoutinePlannerService(session=db, settings=settings)
    await service.delete_routine(user_id=principal.user_id, routine_id=routine_id)
    return ApiResponse(data={"status": "deleted"}, meta=meta)
