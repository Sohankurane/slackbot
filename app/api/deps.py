"""Reusable FastAPI dependencies."""

from typing import AsyncIterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.db import get_sessionmaker, get_system_sessionmaker
from app.models import AdminUser


async def get_tenant_slug(request: Request) -> str:
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
    sm = get_sessionmaker(tenant_slug)
    async with sm() as session:
        yield session


class APITokenPseudoAdmin:
    """Sentinel returned when authenticated via X-Admin-Token header."""
    id = 0
    username = "api-token"
    is_active = True


async def get_current_admin(request: Request) -> AdminUser | APITokenPseudoAdmin:
    """Returns the authenticated admin user.

    Two methods of authentication, in order:
      1. Cookie session (set by login page)
      2. X-Admin-Token header (for API/curl)
    """
    # cookie session
    admin_id = request.session.get("admin_user_id") if hasattr(request, "session") else None
    if admin_id:
        sm = get_system_sessionmaker()
        async with sm() as session:
            user = await session.get(AdminUser, admin_id)
            if user and user.is_active:
                return user
        # Stale session — clear it
        try:
            request.session.clear()
        except Exception:
            pass

    # shared token header (kept for automation/curl)
    header_token = request.headers.get("x-admin-token")
    expected = get_settings().admin_token
    if header_token and header_token == expected:
        return APITokenPseudoAdmin()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="not_authenticated",
    )

require_admin_token = get_current_admin