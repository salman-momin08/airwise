from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

os.environ.setdefault("APP_ENV", "test")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app import models as _models  # noqa: F401
from app.core.config import Settings, get_settings
from app.core.rate_limit import rate_limiter
from app.db.base import Base
from app.db.session import get_db_session
from app.integrations.air_quality.provider import reset_air_quality_circuit_breakers
from app.integrations.email.provider import ConsoleEmailProvider
from app.main import create_app
from app.services.air_quality.cache import telemetry_cache
from app.services.alerts.alert_service import alert_deduplicator


@pytest_asyncio.fixture
async def db_engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    db_file = tmp_path / "airwise_test.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file.as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def api_client(db_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    os.environ["APP_ENV"] = "test"
    get_settings.cache_clear()
    rate_limiter.reset_local_state()
    telemetry_cache.clear_local()
    alert_deduplicator.reset_local_state()
    reset_air_quality_circuit_breakers()
    ConsoleEmailProvider.last_outbox.clear()

    test_settings = Settings(
        app_env="test",
        auth_secret_key="test-only-cryptographic-random-secret-key-at-least-32-bytes",
        auth_cookie_secure=False,
        frontend_url="http://localhost:3000",
        backend_url="http://localhost:8000",
        cron_secret="test-cron-secret-value-123456",
    )

    session_factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        autoflush=False,
    )

    async def _override_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    from app.api.dependencies import get_app_settings

    app = create_app()
    app.dependency_overrides[get_db_session] = _override_db_session
    app.dependency_overrides[get_app_settings] = lambda: test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        yield client
