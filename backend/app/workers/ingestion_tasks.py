from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.air_quality.telemetry_service import AirQualityTelemetryService
from app.workers.celery_app import celery_app

async def _run_priority_ingestion() -> dict[str, int]:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = AirQualityTelemetryService(session=session, settings=settings)
        return await service.ingest_priority_cities()

@celery_app.task(
    name="app.workers.ingestion_tasks.poll_air_quality_sources",
    bind=True,
    max_retries=3,
)
def poll_air_quality_sources(self: object) -> dict[str, object]:
    """Scheduled idempotent task to poll enabled air quality providers and warm Redis cache."""
    stats = asyncio.run(_run_priority_ingestion())
    return {"status": "completed", **stats}
