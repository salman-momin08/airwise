from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    AuthenticatedPrincipal,
    enforce_csrf_protection,
    get_app_settings,
    get_client_ip,
    get_response_meta,
    require_authenticated_user,
)
from app.core.config import Settings
from app.db.session import get_db_session
from app.schemas.common import ApiResponse, ResponseMeta
from app.schemas.identity import (
    GazetteerLocationMatch,
    SavedLocationCreateRequest,
    SavedLocationData,
    SavedLocationUpdateRequest,
)
from app.services.location.location_service import LocationService, search_gazetteer

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/search", response_model=ApiResponse[list[GazetteerLocationMatch]])
async def search_cities(
    q: Annotated[str, Query(min_length=1, max_length=80)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[list[GazetteerLocationMatch]]:
    matches = search_gazetteer(q)
    return ApiResponse(data=matches, meta=meta)


@router.get("", response_model=ApiResponse[list[SavedLocationData]])
async def list_saved_locations(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[list[SavedLocationData]]:
    service = LocationService(session=db, settings=settings)
    items = await service.list_locations(user_id=principal.user_id)
    return ApiResponse(data=items, meta=meta)


@router.post(
    "",
    response_model=ApiResponse[SavedLocationData],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_csrf_protection)],
)
async def create_saved_location(
    payload: SavedLocationCreateRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[SavedLocationData]:
    service = LocationService(session=db, settings=settings)
    created = await service.create_location(
        user_id=principal.user_id,
        payload=payload,
        client_ip=get_client_ip(request),
    )
    return ApiResponse(data=created, meta=meta)


@router.patch(
    "/{location_id}",
    response_model=ApiResponse[SavedLocationData],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def update_saved_location(
    location_id: UUID,
    payload: SavedLocationUpdateRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[SavedLocationData]:
    service = LocationService(session=db, settings=settings)
    updated = await service.update_location(
        user_id=principal.user_id,
        location_id=location_id,
        payload=payload,
        client_ip=get_client_ip(request),
    )
    return ApiResponse(data=updated, meta=meta)


@router.delete(
    "/{location_id}",
    response_model=ApiResponse[dict[str, str]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def delete_saved_location(
    location_id: UUID,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[dict[str, str]]:
    service = LocationService(session=db, settings=settings)
    await service.delete_location(
        user_id=principal.user_id,
        location_id=location_id,
        client_ip=get_client_ip(request),
    )
    return ApiResponse(data={"status": "location_deleted"}, meta=meta)
