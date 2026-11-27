from __future__ import annotations

import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

def _use_serverless_null_pool() -> bool:
    settings = get_settings()
    return (
        settings.database_serverless_pool
        or os.getenv("VERCEL") == "1"
        or settings.database_url.startswith("sqlite")
    )

def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        if _use_serverless_null_pool():
            connect_args = (
                {"statement_cache_size": 0, "prepared_statement_cache_size": 0}
                if settings.database_url.startswith("postgresql+asyncpg")
                else {}
            )
            _engine = create_async_engine(
                settings.database_url,
                poolclass=NullPool,
                connect_args=connect_args,
                echo=settings.debug,
            )
        else:
            _engine = create_async_engine(
                settings.database_url,
                pool_pre_ping=True,
                echo=settings.debug,
            )
    return _engine

def reset_db_engine() -> None:
    """Reset cached engine and session factory (used in isolated test fixtures)."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None

def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory

async def get_db_session() -> AsyncIterator[AsyncSession]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
