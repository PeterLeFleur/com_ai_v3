"""
Database Session Management for COM-AI v3 (MEM-001)
Task ID: MEM-001
Component: Database Layer - Connection Management

Provides:
- Async SQLAlchemy engine configured for PostgreSQL
- Async session factory for dependency injection
- Context manager for transaction handling (idempotent commit/rollback)
- Connection pooling with settings- and env-driven knobs

Settings / Env knobs (all optional; safe defaults used if absent):
  * Echo SQL:
      - Env: DB_ECHO=true|false
      - Settings: settings.db_echo: bool
  * Pooling:
      - Disable pooling (use NullPool): DB_DISABLE_POOL=1 | settings.db_disable_pool=True | settings.testing=True
      - Pool size: DB_POOL_SIZE (int) | settings.db_pool_size
      - Max overflow: DB_MAX_OVERFLOW (int) | settings.db_max_overflow
      - Pre-ping: DB_POOL_PRE_PING=true|false | settings.db_pool_pre_ping
      - Recycle seconds: DB_POOL_RECYCLE_SECONDS (int) | settings.db_pool_recycle_seconds

Usage:
    from src.api.db.session import get_db, init_db_engine

    # at startup (optional override for echo):
    init_db_engine(echo=None)  # default: pulled from settings/env

    # in a route:
    async def handler(..., db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(User))
        return result.scalars().all()
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool

from src.utils.config import get_settings  # loads .env-backed settings


# -------------------------------------------------------------------
# Global engine + session factory (initialized once at app startup)
# -------------------------------------------------------------------
_engine: Optional[AsyncEngine] = None
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_database_url() -> str:
    """
    Construct PostgreSQL connection URL from settings.

    Returns:
        str: postgresql+asyncpg://user:pass@host:port/dbname
    """
    settings = get_settings()
    return (
        "postgresql+asyncpg://"
        f"{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}"
        f"/{settings.postgres_db}"
    )


def _bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except Exception:
        return default


def _build_engine_kwargs():
    """
    Build keyword args for create_async_engine() from settings + env vars.
    Env wins over settings when present. All keys are optional.
    """
    settings = get_settings()

    # Echo SQL
    echo = _bool_env("DB_ECHO", getattr(settings, "db_echo", False))

    # Pooling toggles
    disable_pool = (
        _bool_env("DB_DISABLE_POOL", False)
        or bool(getattr(settings, "db_disable_pool", False))
        or bool(getattr(settings, "testing", False))  # tests often prefer NullPool
    )

    pool_pre_ping = _bool_env("DB_POOL_PRE_PING", getattr(settings, "db_pool_pre_ping", True))
    pool_recycle = _int_env("DB_POOL_RECYCLE_SECONDS", getattr(settings, "db_pool_recycle_seconds", 3600))
    pool_size = _int_env("DB_POOL_SIZE", getattr(settings, "db_pool_size", 5))
    max_overflow = _int_env("DB_MAX_OVERFLOW", getattr(settings, "db_max_overflow", 10))

    kwargs = {
        "echo": echo,
        "pool_pre_ping": pool_pre_ping,
    }

    if disable_pool:
        # Use NullPool (no connection reuse). Good for tests or special cases.
        kwargs["poolclass"] = NullPool
    else:
        # QueuePool settings (defaults match your current runbook).
        kwargs["pool_size"] = pool_size
        kwargs["max_overflow"] = max_overflow
        kwargs["pool_recycle"] = pool_recycle

    return kwargs


def init_db_engine(*, echo: Optional[bool] = None) -> AsyncEngine:
    """
    Initialize the async SQLAlchemy engine (call once at startup).

    Args:
        echo: Optional override for SQL echo.
              If None, respect DB_ECHO/settings.db_echo.

    Returns:
        AsyncEngine: configured async database engine
    """
    global _engine, _async_session_factory

    if _engine is not None:
        return _engine

    database_url = get_database_url()
    engine_kwargs = _build_engine_kwargs()
    if echo is not None:
        engine_kwargs["echo"] = bool(echo)

    _engine = create_async_engine(
        database_url,
        **engine_kwargs,
    )

    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,    # keep instances usable after commit
        autoflush=False,           # explicit flush preferred in services
    )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Return the async session factory (requires init_db_engine() first).
    """
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db_engine() at startup.")
    return _async_session_factory


def _has_active_tx(session: AsyncSession) -> bool:
    """
    Idempotent guard across SQLAlchemy 1.4/2.x.

    - 2.x/1.4+: AsyncSession.in_transaction() exists and returns a Transaction or None.
    - Older fallbacks can check get_transaction().
    """
    if hasattr(session, "in_transaction"):
        return bool(session.in_transaction())
    get_tx = getattr(session, "get_transaction", None)
    return bool(get_tx and get_tx() is not None)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.

    Lifecycle:
      - Creates session from factory
      - Yields to caller
      - Commits on success **iff** a transaction is active (idempotent)
      - Rolls back on error **iff** a transaction is active
      - Closes session
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            # ✅ Idempotent commit — prevents double-commit when routes already committed
            if _has_active_tx(session):
                await session.commit()
        except Exception:
            # ✅ Only rollback if a tx is active
            if _has_active_tx(session):
                await session.rollback()
            raise
        finally:
            await session.close()


async def get_db_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency injection wrapper.

    Example:
        @router.post("/...")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with get_db_session() as session:
        yield session


async def dispose_db_engine() -> None:
    """
    Dispose of the engine and close all pooled connections (shutdown).
    """
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


# Convenience helper for ad-hoc queries outside of FastAPI DI
async def execute_query(query_func):
    """
    Execute a database query with automatic session lifecycle.

    Args:
        query_func: async function that accepts AsyncSession and returns a result

    Returns:
        Result of query_func(session)
    """
    async with get_db_session() as session:
        return await query_func(session)


# Health check helper
async def check_db_connection() -> bool:
    """
    Verify database connection is healthy (used by /api/health/db).

    Returns:
        bool: True if a simple SELECT 1 succeeds, else False.
    """
    try:
        async with get_db_session() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception:
        return False


# Alias for FastAPI dependency injection (standard naming)
get_db = get_db_session_dependency
