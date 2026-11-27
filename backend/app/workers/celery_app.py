"""Celery application configuration, Redis broker bindings, and periodic beat schedule."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings, is_valid_redis_url

settings = get_settings()
_celery_redis_url = settings.redis_url if is_valid_redis_url(settings.redis_url) else None

celery_app = Celery(
    "airwise_workers",
    broker=_celery_redis_url or "memory://",
    backend=_celery_redis_url or "cache+memory://",
    include=[
        "app.workers.ingestion_tasks",
        "app.workers.knowledge_tasks",
        "app.workers.alert_tasks",
        "app.workers.maintenance_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "ingest-priority-city-air-quality": {
            "task": "app.workers.ingestion_tasks.poll_air_quality_sources",
            "schedule": crontab(minute="*/15"),
        },
        "evaluate-smart-aqi-alerts": {
            "task": "app.workers.alert_tasks.evaluate_active_alert_rules",
            "schedule": crontab(minute="*/15"),
        },
        "purge-expired-sessions": {
            "task": "app.workers.maintenance_tasks.cleanup_expired_sessions",
            "schedule": crontab(hour=2, minute=30),
        },
    },
)
