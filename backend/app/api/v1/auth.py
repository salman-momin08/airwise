from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    AuthenticatedPrincipal,
    RequestPrincipal,
    attach_session_cookies,
    clear_session_cookies,
    enforce_csrf_protection,
    get_app_settings,
    get_client_ip,
    get_current_principal,
    get_response_meta,
    require_authenticated_user,
)
from app.core.config import Settings
from app.core.rate_limit import rate_limiter
from app.core.security import SESSION_COOKIE_NAME, generate_secure_token
from app.db.session import get_db_session
from app.integrations.email.provider import get_email_provider
from app.schemas.common import ApiResponse, ResponseMeta
from app.schemas.identity import (
    AuthPrincipalData,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionItem,
    VerifyEmailRequest,
)
from app.services.auth.auth_service import AuthService
from app.services.auth.oauth import GoogleOAuthAdapterStub

router = APIRouter(prefix="/auth", tags=["auth"])

def _build_auth_service(db: AsyncSession, settings: Settings) -> AuthService:
    return AuthService(session=db, settings=settings, email_provider=get_email_provider())

@router.post(
    "/register",
    response_model=ApiResponse[AuthPrincipalData],
    status_code=status.HTTP_201_CREATED,
)
async def register_account(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[AuthPrincipalData]:
    client_ip = get_client_ip(request)
    await rate_limiter.check("auth_register", client_ip or "anon", limit=8, window_seconds=300)
    service = _build_auth_service(db, settings)
    bundle = await service.register_user(
        payload,
        client_ip=client_ip,
        user_agent=request.headers.get("User-Agent"),
    )
    attach_session_cookies(response, bundle, settings)
    return ApiResponse(data=bundle.principal, meta=meta)

@router.post("/login", response_model=ApiResponse[AuthPrincipalData])
async def login_account(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[AuthPrincipalData]:
    client_ip = get_client_ip(request)
    await rate_limiter.check("auth_login", client_ip or "anon", limit=10, window_seconds=300)
    service = _build_auth_service(db, settings)
    bundle = await service.login_user(
        payload,
        client_ip=client_ip,
        user_agent=request.headers.get("User-Agent"),
    )
    attach_session_cookies(response, bundle, settings)
    return ApiResponse(data=bundle.principal, meta=meta)

@router.post(
    "/logout",
    response_model=ApiResponse[dict[str, str]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def logout_account(
    request: Request,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[dict[str, str]]:
    service = _build_auth_service(db, settings)
    await service.logout_current_session(
        user_id=principal.user_id,
        session_id=principal.session_id,
        client_ip=get_client_ip(request),
    )
    clear_session_cookies(response, settings)
    return ApiResponse(data={"status": "logged_out"}, meta=meta)

@router.post(
    "/refresh",
    response_model=ApiResponse[AuthPrincipalData],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def rotate_session_token(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[AuthPrincipalData]:
    raw_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    service = _build_auth_service(db, settings)
    bundle = await service.rotate_session(
        raw_session_token=raw_cookie,
        client_ip=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )
    attach_session_cookies(response, bundle, settings)
    return ApiResponse(data=bundle.principal, meta=meta)

@router.post("/forgot-password", response_model=ApiResponse[dict[str, str]])
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[dict[str, str]]:
    client_ip = get_client_ip(request)
    await rate_limiter.check("auth_forgot", client_ip or "anon", limit=5, window_seconds=300)
    service = _build_auth_service(db, settings)
    await service.request_password_reset(payload.email, client_ip=client_ip)
    return ApiResponse(
        data={
            "message": (
                "If an account exists for that email address, "
                "a password reset link has been sent."
            )
        },
        meta=meta,
    )

@router.post("/reset-password", response_model=ApiResponse[dict[str, str]])
async def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[dict[str, str]]:
    client_ip = get_client_ip(request)
    await rate_limiter.check("auth_reset", client_ip or "anon", limit=5, window_seconds=300)
    service = _build_auth_service(db, settings)
    await service.reset_password(payload, client_ip=client_ip)
    clear_session_cookies(response, settings)
    return ApiResponse(data={"status": "password_reset_completed"}, meta=meta)

@router.post("/verify-email", response_model=ApiResponse[dict[str, str]])
async def verify_email_address(
    payload: VerifyEmailRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[dict[str, str]]:
    service = _build_auth_service(db, settings)
    await service.verify_email(payload.token, client_ip=get_client_ip(request))
    return ApiResponse(data={"status": "email_verified"}, meta=meta)

@router.get("/me", response_model=ApiResponse[AuthPrincipalData])
async def get_current_session_principal(
    principal: Annotated[RequestPrincipal, Depends(get_current_principal)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[AuthPrincipalData]:
    return ApiResponse(
        data=AuthPrincipalData(
            user_id=str(principal.user_id) if principal.user_id else None,
            email=principal.email,
            display_name=principal.display_name,
            role=principal.role.value,
            is_email_verified=principal.is_email_verified,
            preferred_aqi_standard=principal.preferred_aqi_standard,
            session_id=str(principal.session_id) if principal.session_id else None,
        ),
        meta=meta,
    )

@router.get("/sessions", response_model=ApiResponse[list[SessionItem]])
async def list_active_sessions(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[list[SessionItem]]:
    service = _build_auth_service(db, settings)
    sessions = await service.list_sessions(
        user_id=principal.user_id,
        current_session_id=principal.session_id,
    )
    return ApiResponse(data=sessions, meta=meta)

@router.delete(
    "/sessions/{session_id}",
    response_model=ApiResponse[dict[str, str]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def revoke_session(
    session_id: UUID,
    request: Request,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[dict[str, str]]:
    service = _build_auth_service(db, settings)
    await service.revoke_specific_session(
        user_id=principal.user_id,
        target_session_id=session_id,
        client_ip=get_client_ip(request),
    )
    if principal.session_id == session_id:
        clear_session_cookies(response, settings)
    return ApiResponse(data={"status": "session_revoked"}, meta=meta)

@router.post(
    "/sessions/revoke-others",
    response_model=ApiResponse[dict[str, int]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def revoke_other_sessions(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[dict[str, int]]:
    service = _build_auth_service(db, settings)
    revoked = await service.revoke_other_sessions(
        user_id=principal.user_id,
        current_session_id=principal.session_id,
        client_ip=get_client_ip(request),
    )
    return ApiResponse(data={"revoked_count": revoked}, meta=meta)

@router.get("/oauth/google/status", response_model=ApiResponse[dict[str, object]])
async def get_google_oauth_status(
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[dict[str, object]]:
    adapter = GoogleOAuthAdapterStub(settings)
    is_ready = adapter.is_configured()
    return ApiResponse(
        data={
            "provider": "google",
            "enabled": is_ready,
            "authorization_url": (
                adapter.build_authorization_url(generate_secure_token(16)) if is_ready else None
            ),
        },
        meta=meta,
    )
