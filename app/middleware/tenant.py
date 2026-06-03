"""Tenant middleware."""

import json
import logging
from typing import Optional
from urllib.parse import parse_qs

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.context import clear_context, set_context
from app.core.db import get_system_sessionmaker
from app.models import Tenant

logger = logging.getLogger(__name__)

_PUBLIC_PREFIXES = (
    "/health",
    "/static",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
    "/admin",
    "/api/admin",
    "/user",
    "/api/user",
)

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path == "/" or path.startswith(_PUBLIC_PREFIXES):
            return await call_next(request)

        try:
            tenant = await self._resolve_tenant(request)
        except Exception:
            logger.exception("Tenant resolution failed")
            return JSONResponse(
                {"error": "tenant_resolution_failed"}, status_code=500
            )

        if tenant is None:
            if path.startswith("/slack"):
                return await call_next(request)
            return JSONResponse({"error": "tenant_not_found"}, status_code=404)

        request.state.tenant_id = tenant.id
        request.state.tenant_slug = tenant.slug
        request.state.slack_team_id = tenant.slack_team_id

        # Set contextvars for logging
        set_context(tenant_id=tenant.id, tenant_slug=tenant.slug)

        try:
            return await call_next(request)
        finally:
            clear_context()

    async def _resolve_tenant(self, request: Request) -> Optional[Tenant]:
        path = request.url.path

        if path.startswith("/slack"):
            team_id = await self._team_id_from_slack(request)
            if not team_id:
                return None
            return await self._lookup_by_team_id(team_id)

        return None

    async def _team_id_from_slack(self, request: Request) -> Optional[str]:
        body = await request.body() 
        if not body:
            return None

        ctype = request.headers.get("content-type", "")

        if "application/json" in ctype:
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                return None
            # URL verification has no team_id
            if payload.get("type") == "url_verification":
                return None
            return payload.get("team_id") or (
                payload.get("team", {}) or {}
            ).get("id")

        if "application/x-www-form-urlencoded" in ctype:
            parsed = parse_qs(body.decode("utf-8", errors="ignore"))
            
            if "payload" in parsed:
                try:
                    inner = json.loads(parsed["payload"][0])
                    return inner.get("team", {}).get("id") or inner.get("team_id")
                except json.JSONDecodeError:
                    return None
            vals = parsed.get("team_id")
            return vals[0] if vals else None

        return None

    async def _lookup_by_team_id(self, team_id: str) -> Optional[Tenant]:
        sm = get_system_sessionmaker()
        async with sm() as session:
            result = await session.execute(
                select(Tenant).where(
                    Tenant.slack_team_id == team_id, Tenant.is_active.is_(True)
                )
            )
            return result.scalar_one_or_none()

    async def _lookup_by_slug(self, slug: str) -> Optional[Tenant]:
        sm = get_system_sessionmaker()
        async with sm() as session:
            result = await session.execute(
                select(Tenant).where(
                    Tenant.slug == slug, Tenant.is_active.is_(True)
                )
            )
            return result.scalar_one_or_none()