from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.integrations.email.provider import get_email_provider
from app.services.auth.auth_service import AuthService
from app.workers.celery_app import celery_app


async def _run_session_cleanup() -> int:
    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = AuthService(
            session=session,
            settings=settings,
            email_provider=get_email_provider(),
        )
        return await service.cleanup_expired_sessions()


@celery_app.task(name="app.workers.maintenance_tasks.cleanup_expired_sessions")
def cleanup_expired_sessions() -> dict[str, object]:
    """Purge expired/revoked user_sessions according to 30-day retention policy."""
    purged_count = asyncio.run(_run_session_cleanup())
    return {"status": "completed", "purged_expired_sessions": purged_count}
