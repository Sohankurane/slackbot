"""Reusable FastAPI dependencies."""

from typing import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.db import get_sessionmaker


async def get_tenant_slug(request: Request) -> str:
    """Pulls the tenant slug that the middleware put on request.state."""
    slug = getattr(request.state, "tenant_slug", None)
    if not slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant_not_resolved",
        )
    return slug


async def get_db(
    tenant_slug: str = Depends(get_tenant_slug),
) -> AsyncIterator[AsyncSession]:
    """Yields a session bound to the current tenant's pool."""
    sm = get_sessionmaker(tenant_slug)
    async with sm() as session:
        yield session


async def require_admin_token(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """Simple shared-secret auth for admin endpoints."""
    expected = get_settings().admin_token
    if not x_admin_token or x_admin_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_admin_token",
        )