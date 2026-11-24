from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Header, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import AirWiseError, AuthorizationError
from app.core.logging import configure_logging
from app.core.middleware import CorrelationAndSecurityHeadersMiddleware
from app.core.telemetry import telemetry_registry
from app.schemas.common import ErrorDetail, ErrorResponse, HealthStatus


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(debug=settings.debug)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="GenAI-Powered Smog & Air Pollution Lifestyle Assistant API",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
        lifespan=lifespan,
    )

    app.add_middleware(CorrelationAndSecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )

    @app.exception_handler(AirWiseError)
    async def handle_domain_error(request: Request, exc: AirWiseError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        payload = ErrorResponse(
            error=ErrorDetail(code=exc.code, message=exc.message, request_id=request_id)
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        payload = ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message=f"Invalid request parameters ({len(exc.errors())} validation error(s)).",
                request_id=request_id,
            )
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=payload.model_dump(),
        )

    @app.get("/health/live", response_model=HealthStatus, tags=["system"])
    async def liveness_probe() -> HealthStatus:
        return HealthStatus(
            status="ok",
            service=settings.otel_service_name,
            environment=settings.app_env,
        )

    @app.get("/health/ready", response_model=HealthStatus, tags=["system"])
    async def readiness_probe() -> HealthStatus:
        return HealthStatus(
            status="ready",
            service=settings.otel_service_name,
            environment=settings.app_env,
            checks={"config": "ok", "aqi_provider_mode": settings.air_quality_provider},
        )

    @app.get("/metrics", response_class=PlainTextResponse, tags=["system"])
    async def prometheus_metrics(
        x_metrics_token: Annotated[str | None, Header(alias="X-Metrics-Token")] = None,
    ) -> PlainTextResponse:
        if settings.metrics_internal_token and not hmac.compare_digest(
            x_metrics_token or "",
            settings.metrics_internal_token,
        ):
            raise AuthorizationError("Metrics scrape token is invalid.")
        lines = [
            "# HELP airwise_http_requests_total Total HTTP requests processed",
            "# TYPE airwise_http_requests_total counter",
            f"airwise_http_requests_total {telemetry_registry.http_requests_total}",
            "# HELP airwise_llm_fallback_total Total deterministic AI fallback activations",
            "# TYPE airwise_llm_fallback_total counter",
            f"airwise_llm_fallback_total {telemetry_registry.llm_fallback_total}",
        ]
        return PlainTextResponse("\n".join(lines) + "\n")

    app.include_router(api_v1_router)
    return app


app = create_app()
