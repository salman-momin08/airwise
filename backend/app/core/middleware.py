"""Request correlation ID, latency metrics, cache-control, and security headers middleware."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.telemetry import telemetry_registry

REQUEST_ID_HEADER = "X-Request-ID"
_NO_STORE_PATH_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/users",
    "/api/v1/assistant",
    "/api/v1/admin",
    "/api/v1/locations",
    "/api/v1/routines",
    "/api/v1/recommendations",
    "/api/v1/alerts",
    "/api/v1/notifications",
    "/api/v1/system",
    "/metrics",
)
_OPENAPI_DOC_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"})


class CorrelationAndSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach correlation request IDs, latency metrics, and HTTP security headers."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming_id = request.headers.get(REQUEST_ID_HEADER)
        try:
            request_id = str(uuid.UUID(incoming_id)) if incoming_id else str(uuid.uuid4())
        except ValueError:
            request_id = str(uuid.uuid4())

        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000.0
        telemetry_registry.record_request(duration_ms=duration_ms, status_code=response.status_code)

        path = request.url.path
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(self), camera=(), microphone=(), payment=()"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"
        if path not in _OPENAPI_DOC_PATHS and "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )
        if "Cache-Control" not in response.headers and (
            request.method != "GET" or path.startswith(_NO_STORE_PATH_PREFIXES)
        ):
            response.headers["Cache-Control"] = "no-store"
        if get_settings().auth_cookie_secure:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response
