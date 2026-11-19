from __future__ import annotations

from app.workers.celery_app import celery_app


@celery_app.task(
    name="app.workers.ingestion_tasks.poll_air_quality_sources",
    bind=True,
    max_retries=3,
)
def poll_air_quality_sources(self: object) -> dict[str, str]:
    """Scheduled idempotent task to poll enabled air quality providers and warm Redis cache."""
    return {"status": "scheduled_stub_ready_for_phase_3"}
