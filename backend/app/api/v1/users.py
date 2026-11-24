from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    AuthenticatedPrincipal,
    clear_session_cookies,
    enforce_csrf_protection,
    get_app_settings,
    get_client_ip,
    get_response_meta,
    require_authenticated_user,
)
from app.core.config import Settings
from app.db.session import get_db_session
from app.schemas.common import ApiResponse, ResponseMeta
from app.schemas.identity import AccountExportData, UpdateUserMeRequest, UserMeData
from app.services.auth.user_service import UserAccountService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ApiResponse[UserMeData])
async def get_user_profile(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[UserMeData]:
    service = UserAccountService(session=db, settings=settings)
    data = await service.get_me(user_id=principal.user_id)
    return ApiResponse(data=data, meta=meta)


@router.patch(
    "/me",
    response_model=ApiResponse[UserMeData],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def update_user_profile_and_preferences(
    payload: UpdateUserMeRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[UserMeData]:
    service = UserAccountService(session=db, settings=settings)
    updated = await service.update_me(
        user_id=principal.user_id,
        payload=payload,
        client_ip=get_client_ip(request),
    )
    return ApiResponse(data=updated, meta=meta)


@router.get("/me/export", response_model=ApiResponse[AccountExportData])
async def export_user_account_data(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[AccountExportData]:
    service = UserAccountService(session=db, settings=settings)
    export_payload = await service.export_my_data(
        user_id=principal.user_id,
        client_ip=get_client_ip(request),
    )
    return ApiResponse(data=export_payload, meta=meta)


@router.delete(
    "/me",
    response_model=ApiResponse[dict[str, str]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def delete_user_account(
    request: Request,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[dict[str, str]]:
    service = UserAccountService(session=db, settings=settings)
    await service.delete_my_account(
        user_id=principal.user_id,
        client_ip=get_client_ip(request),
    )
    clear_session_cookies(response, settings)
    return ApiResponse(data={"status": "account_deleted"}, meta=meta)
