from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import UserRole, verify_csrf_double_submit
from app.schemas.common import ResponseMeta


@dataclass(frozen=True)
class RequestPrincipal:
    user_id: uuid.UUID | None
    role: UserRole


def get_response_meta(request: Request) -> ResponseMeta:
    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return ResponseMeta(request_id=request_id)


def get_current_principal(request: Request) -> RequestPrincipal:
    """Resolve authenticated principal from session middleware (Guest when unauthenticated)."""
    principal = getattr(request.state, "principal", None)
    if isinstance(principal, RequestPrincipal):
        return principal
    return RequestPrincipal(user_id=None, role=UserRole.GUEST)


def require_authenticated_user(
    principal: Annotated[RequestPrincipal, Depends(get_current_principal)],
) -> RequestPrincipal:
    if principal.user_id is None or principal.role == UserRole.GUEST:
        raise AuthenticationError()
    return principal


def require_admin_user(
    principal: Annotated[RequestPrincipal, Depends(require_authenticated_user)],
) -> RequestPrincipal:
    if principal.role != UserRole.ADMIN:
        raise AuthorizationError("Administrator privileges are required.")
    return principal


def enforce_csrf_protection(
    request: Request,
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        csrf_cookie = request.cookies.get("airwise_csrf")
        if not verify_csrf_double_submit(csrf_cookie, x_csrf_token):
            raise AuthorizationError("CSRF token validation failed.")


def get_app_settings() -> Settings:
    return get_settings()
