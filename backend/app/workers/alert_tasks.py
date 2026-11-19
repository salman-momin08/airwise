from __future__ import annotations

from app.workers.celery_app import celery_app


@celery_app.task(
    name="app.workers.alert_tasks.evaluate_active_alert_rules",
    bind=True,
    max_retries=3,
)
def evaluate_active_alert_rules(self: object) -> dict[str, str]:
    """Evaluate user AQI thresholds with Redis deduplication, cooldowns, and quiet hours."""
    return {"status": "scheduled_stub_ready_for_phase_6"}
