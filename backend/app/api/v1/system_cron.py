"""Bearer-authenticated scheduled maintenance, AQI ingestion, and alert evaluation cron routes."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_app_settings, get_response_meta
from app.core.config import Settings
from app.core.exceptions import AuthorizationError
from app.db.session import get_db_session
from app.integrations.email.provider import get_email_provider
from app.schemas.common import ApiResponse, ResponseMeta
from app.services.air_quality.telemetry_service import AirQualityTelemetryService
from app.services.alerts.alert_service import SmartAlertService
from app.services.auth.auth_service import AuthService

router = APIRouter(prefix="/system", tags=["system"])


def _verify_cron_secret(settings: Settings, authorization: str | None) -> None:
    if not settings.cron_secret:
        raise AuthorizationError("CRON_SECRET is not configured on this instance.")
    expected_header = f"Bearer {settings.cron_secret}"
    if not authorization or not hmac.compare_digest(authorization, expected_header):
        raise AuthorizationError("Invalid cron authorization bearer secret.")


@router.get(
    "/cron/daily-maintenance",
    response_model=ApiResponse[dict[str, object]],
)
async def run_daily_maintenance_cron(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> ApiResponse[dict[str, object]]:
    """Authenticated Vercel Cron endpoint for daily session retention & telemetry refresh."""
    _verify_cron_secret(settings, authorization)

    auth_service = AuthService(
        session=db,
        settings=settings,
        email_provider=get_email_provider(),
    )
    purged_sessions = await auth_service.cleanup_expired_sessions()
    aq_service = AirQualityTelemetryService(session=db, settings=settings)
    ingestion_stats = await aq_service.ingest_priority_cities()
    return ApiResponse(
        data={
            "status": "completed",
            "purged_expired_sessions": purged_sessions,
            "telemetry_ingestion": ingestion_stats,
        },
        meta=meta,
    )


@router.get(
    "/cron/ingest-air-quality",
    response_model=ApiResponse[dict[str, object]],
)
async def run_air_quality_ingestion_cron(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> ApiResponse[dict[str, object]]:
    """Authenticated cron endpoint for scheduled priority-city AQI station & cache ingestion."""
    _verify_cron_secret(settings, authorization)
    aq_service = AirQualityTelemetryService(session=db, settings=settings)
    stats = await aq_service.ingest_priority_cities()
    return ApiResponse(data={"status": "completed", **stats}, meta=meta)


@router.get(
    "/cron/evaluate-alerts",
    response_model=ApiResponse[dict[str, object]],
)
async def run_alert_evaluation_cron(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> ApiResponse[dict[str, object]]:
    """Authenticated cron endpoint for scheduled smart AQI alert evaluation."""
    _verify_cron_secret(settings, authorization)
    alert_service = SmartAlertService(session=db, settings=settings)
    summary = await alert_service.evaluate_active_rules()
    return ApiResponse(
        data={"status": "completed", **summary.model_dump(mode="json")},
        meta=meta,
    )
