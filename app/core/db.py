"""Tenant-aware database layer."""

import logging
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

_engines: dict[str, AsyncEngine] = {}
_sessionmakers: dict[str, async_sessionmaker[AsyncSession]] = {}


def _build_url_for_tenant(tenant_slug: str) -> str:
    """Right now: same URL for every tenant. Later: look up per-tenant URL
    from a 'tenants' config table."""
    return get_settings().database_url


def get_engine(tenant_slug: str) -> AsyncEngine:
    """Return (or lazily create) the engine for a tenant."""
    if tenant_slug not in _engines:
        url = _build_url_for_tenant(tenant_slug)
        engine = create_async_engine(
            url,
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=False,
        )
        _engines[tenant_slug] = engine
        _sessionmakers[tenant_slug] = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
        logger.info("Created DB engine for tenant=%s", tenant_slug)
    return _engines[tenant_slug]


def get_sessionmaker(tenant_slug: str) -> async_sessionmaker[AsyncSession]:
    get_engine(tenant_slug)  # ensures sessionmaker exists too
    return _sessionmakers[tenant_slug]


async def get_session(tenant_slug: str) -> AsyncIterator[AsyncSession]:
    """Yield a session for the given tenant. Use with `async for` or as a dep."""
    sm = get_sessionmaker(tenant_slug)
    async with sm() as session:
        yield session

_system_engine: AsyncEngine | None = None
_system_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_system_engine() -> AsyncEngine:
    global _system_engine, _system_sessionmaker
    if _system_engine is None:
        _system_engine = create_async_engine(
            get_settings().database_url,
            pool_size=2,
            max_overflow=2,
            pool_pre_ping=True,
        )
        _system_sessionmaker = async_sessionmaker(
            _system_engine, expire_on_commit=False, class_=AsyncSession
        )
    return _system_engine


def get_system_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_system_engine()
    assert _system_sessionmaker is not None
    return _system_sessionmaker


async def dispose_all() -> None:
    """Called on app shutdown — close all pools cleanly."""
    for slug, engine in list(_engines.items()):
        await engine.dispose()
        logger.info("Disposed DB engine for tenant=%s", slug)
    _engines.clear()
    _sessionmakers.clear()
    if _system_engine is not None:
        await _system_engine.dispose()
        logger.info("Disposed system DB engine")