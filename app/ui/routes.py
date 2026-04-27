"""HTML UI routes — rendered with Jinja2."""

import logging

from fastapi import APIRouter, Request
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
        result = await session.execute(
            select(Tenant).where(Tenant.is_active.is_(True))
        )
        tenants = result.scalars().all()

        tenant_data = []
        for t in tenants:
            bot_result = await session.execute(
                select(Bot).where(Bot.tenant_id == t.id, Bot.is_active.is_(True))
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