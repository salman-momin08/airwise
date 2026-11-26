from __future__ import annotations

import hmac
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import AirWiseError, AuthorizationError
from app.core.logging import configure_logging
from app.core.middleware import CorrelationAndSecurityHeadersMiddleware
from app.core.telemetry import telemetry_registry
from app.db.session import get_db_session
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
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
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
    async def readiness_probe(
        db: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> HealthStatus:
        db_status = "ok"
        try:
            await db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            db_status = "degraded"
        return HealthStatus(
            status="ready" if db_status == "ok" else "degraded",
            service=settings.otel_service_name,
            environment=settings.app_env,
            checks={
                "config": "ok",
                "database": db_status,
                "aqi_provider_mode": settings.air_quality_provider,
                "llm_provider": settings.llm_provider,
            },
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
        p50 = telemetry_registry.percentile_latency_ms(50.0)
        p95 = telemetry_registry.percentile_latency_ms(95.0)
        lines = [
            "# HELP airwise_http_requests_total Total HTTP requests processed",
            "# TYPE airwise_http_requests_total counter",
            f"airwise_http_requests_total {telemetry_registry.http_requests_total}",
            "# HELP airwise_http_errors_total Total 5xx HTTP responses",
            "# TYPE airwise_http_errors_total counter",
            f"airwise_http_errors_total {telemetry_registry.http_errors_total}",
            "# HELP airwise_http_latency_p50_ms Sliding window p50 HTTP latency in milliseconds",
            "# TYPE airwise_http_latency_p50_ms gauge",
            f"airwise_http_latency_p50_ms {p50}",
            "# HELP airwise_http_latency_p95_ms Sliding window p95 HTTP latency in milliseconds",
            "# TYPE airwise_http_latency_p95_ms gauge",
            f"airwise_http_latency_p95_ms {p95}",
            "# HELP airwise_aqi_cache_hits_total Total fresh AQI cache hits",
            "# TYPE airwise_aqi_cache_hits_total counter",
            f"airwise_aqi_cache_hits_total {telemetry_registry.aqi_cache_hits_total}",
            "# HELP airwise_aqi_cache_misses_total Total AQI cache misses",
            "# TYPE airwise_aqi_cache_misses_total counter",
            f"airwise_aqi_cache_misses_total {telemetry_registry.aqi_cache_misses_total}",
            "# HELP airwise_llm_requests_total Total external LLM API generation attempts",
            "# TYPE airwise_llm_requests_total counter",
            f"airwise_llm_requests_total {telemetry_registry.llm_requests_total}",
            "# HELP airwise_llm_fallback_total Total deterministic AI fallback activations",
            "# TYPE airwise_llm_fallback_total counter",
            f"airwise_llm_fallback_total {telemetry_registry.llm_fallback_total}",
        ]
        return PlainTextResponse("\n".join(lines) + "\n")

    app.include_router(api_v1_router)
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        FastAPIInstrumentor.instrument_app(app)
    return app


app = create_app()
