"""Idempotent Celery task evaluating enabled smart AQI alert rules."""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.services.alerts.alert_service import SmartAlertService
from app.workers.celery_app import celery_app


async def _run_alert_evaluation() -> dict[str, object]:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = SmartAlertService(session=session, settings=settings)
        summary = await service.evaluate_active_rules()
        return summary.model_dump(mode="json")


@celery_app.task(
    name="app.workers.alert_tasks.evaluate_active_alert_rules",
    max_retries=3,
)
def evaluate_active_alert_rules() -> dict[str, object]:
    """Evaluate user AQI thresholds with Redis deduplication, cooldowns, and quiet hours."""
    stats = asyncio.run(_run_alert_evaluation())
    return {"status": "completed", **stats}
