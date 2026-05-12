"""HTML UI routes — rendered with Jinja2."""

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.core.db import get_system_sessionmaker
from app.models import Bot, Tenant

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory="app/ui/templates")


@router.get("/admin", response_class=HTMLResponse)
async def dashboard(request: Request):
    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(select(Tenant).order_by(Tenant.id))
        tenants = result.scalars().all()

        tenant_data = []
        for t in tenants:
            bot_result = await session.execute(
                select(Bot).where(Bot.tenant_id == t.id).order_by(Bot.id)
            )
            bots = bot_result.scalars().all()
            tenant_data.append({"tenant": t, "bots": bots})

    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "tenant_data": tenant_data}
    )


@router.get("/admin/compose", response_class=HTMLResponse)
async def compose(request: Request, tenant: str = "prj-sk"):
    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            select(Bot)
            .join(Tenant, Bot.tenant_id == Tenant.id)
            .where(Tenant.slug == tenant, Bot.is_active.is_(True))
        )
        bots = result.scalars().all()

    return templates.TemplateResponse(
        "compose.html", {"request": request, "bots": bots, "tenant": tenant}
    )


@router.get("/admin/manage", response_class=HTMLResponse)
async def manage_tenants(request: Request):
    return templates.TemplateResponse("manage_tenants.html", {"request": request})


@router.get("/admin/manage/{tenant_slug}", response_class=HTMLResponse)
async def manage_bots(request: Request, tenant_slug: str):
    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.slug == tenant_slug)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

    return templates.TemplateResponse(
        "manage_bots.html",
        {"request": request, "tenant": tenant},
    )