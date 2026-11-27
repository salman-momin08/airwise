"""Cookie session resolution, RBAC guards, CSRF verification, and request metadata dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    UserRole,
    is_trusted_origin,
    verify_csrf_double_submit,
)
from app.db.session import get_db_session
from app.integrations.email.provider import get_email_provider
from app.schemas.common import ResponseMeta
from app.schemas.identity import AQIStandardLiteral
from app.services.auth.auth_service import AuthService, IssuedSessionBundle


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    user_id: uuid.UUID
    role: UserRole
    email: str | None = None
    display_name: str | None = None
    is_email_verified: bool = False
    preferred_aqi_standard: AQIStandardLiteral = "india_naqi"
    session_id: uuid.UUID | None = None


@dataclass(frozen=True)
class RequestPrincipal:
    user_id: uuid.UUID | None
    role: UserRole
    email: str | None = None
    display_name: str | None = None
    is_email_verified: bool = False
    preferred_aqi_standard: AQIStandardLiteral = "india_naqi"
    session_id: uuid.UUID | None = None


def get_response_meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return ResponseMeta(request_id=request_id)


def get_app_settings() -> Settings:
    return get_settings()


def get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return None


def attach_session_cookies(
    response: Response,
    bundle: IssuedSessionBundle,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=bundle.raw_session_token,
        max_age=bundle.max_age_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=bundle.raw_csrf_token,
        max_age=bundle.max_age_seconds,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


async def get_current_principal(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> RequestPrincipal:
    """Resolve authenticated principal from HttpOnly session cookie (Guest when absent)."""
    cached = getattr(request.state, "principal", None)
    if isinstance(cached, RequestPrincipal):
        return cached

    raw_cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_cookie:
        guest = RequestPrincipal(user_id=None, role=UserRole.GUEST)
        request.state.principal = guest
        return guest

    auth_service = AuthService(
        session=db,
        settings=settings,
        email_provider=get_email_provider(),
    )
    resolved = await auth_service.resolve_session_cookie(raw_cookie)
    if resolved is None or resolved.user_id is None:
        guest = RequestPrincipal(user_id=None, role=UserRole.GUEST)
        request.state.principal = guest
        return guest

    role_enum = (
        UserRole(resolved.role) if resolved.role in UserRole._value2member_map_ else UserRole.USER
    )
    principal = RequestPrincipal(
        user_id=uuid.UUID(resolved.user_id),
        role=role_enum,
        email=resolved.email,
        display_name=resolved.display_name,
        is_email_verified=resolved.is_email_verified,
        preferred_aqi_standard=resolved.preferred_aqi_standard,
        session_id=uuid.UUID(resolved.session_id) if resolved.session_id else None,
    )
    request.state.principal = principal
    return principal


def require_authenticated_user(
    principal: Annotated[RequestPrincipal, Depends(get_current_principal)],
) -> AuthenticatedPrincipal:
    if principal.user_id is None or principal.role == UserRole.GUEST:
        raise AuthenticationError
    return AuthenticatedPrincipal(
        user_id=principal.user_id,
        role=principal.role,
        email=principal.email,
        display_name=principal.display_name,
        is_email_verified=principal.is_email_verified,
        preferred_aqi_standard=principal.preferred_aqi_standard,
        session_id=principal.session_id,
    )


def require_moderator_or_admin(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
) -> AuthenticatedPrincipal:
    if principal.role not in {UserRole.MODERATOR, UserRole.ADMIN}:
        raise AuthorizationError("Moderator or administrator privileges are required.")
    return principal


def require_admin_user(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)],
) -> AuthenticatedPrincipal:
    if principal.role != UserRole.ADMIN:
        raise AuthorizationError("Administrator privileges are required.")
    return principal


def enforce_csrf_protection(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        allowed_origins = {settings.frontend_url, settings.backend_url}
        if not is_trusted_origin(
            request.headers.get("Origin"),
            request.headers.get("Referer"),
            allowed_origins,
        ):
            raise AuthorizationError(
                message="Untrusted request origin.",
                code="AUTH_CSRF_INVALID",
            )
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        if not verify_csrf_double_submit(csrf_cookie, x_csrf_token):
            raise AuthorizationError(
                message="CSRF token validation failed.",
                code="AUTH_CSRF_INVALID",
            )
