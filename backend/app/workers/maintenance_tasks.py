from __future__ import annotations

from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.maintenance_tasks.cleanup_expired_sessions")
def cleanup_expired_sessions() -> dict[str, str]:
    """Purge expired/revoked user_sessions according to retention policy."""
    return {"status": "scheduled_stub_ready_for_phase_2"}
