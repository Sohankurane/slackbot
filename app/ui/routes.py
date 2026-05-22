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
    
@router.get("/admin/manage/{tenant_slug}/users", response_class=HTMLResponse)
async def manage_users(request: Request, tenant_slug: str):
    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.slug == tenant_slug)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
    return templates.TemplateResponse(
        "manage_users.html",
        {"request": request, "tenant": tenant},
    )

@router.get("/admin/templates", response_class=HTMLResponse)
async def manage_templates(request: Request):
    from app.config import get_settings
    sm = get_system_sessionmaker()
    async with sm() as session:
        from app.models import SlackAppTemplate
        result = await session.execute(
            select(SlackAppTemplate).order_by(SlackAppTemplate.id)
        )
        templates_list = result.scalars().all()
    return templates.TemplateResponse(
        "manage_templates.html",
        {
            "request": request,
            "templates_list": templates_list,
            "public_base_url": get_settings().public_base_url,
        },
    )
    
@router.get("/admin/manage/{tenant_slug}/history", response_class=HTMLResponse)
async def user_history(request: Request, tenant_slug: str, page: int = 1):
    from sqlalchemy import and_, func
    from app.models import Message, SlackUser, Bot

    PAGE_SIZE = 25
    page = max(1, page)
    offset = (page - 1) * PAGE_SIZE

    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Total count for pagination
        total = (await session.execute(
            select(func.count(Message.id)).where(Message.tenant_id == tenant.id)
        )).scalar_one()

        # Joined page of rows
        stmt = (
            select(Message, SlackUser, Bot)
            .outerjoin(SlackUser, and_(
                SlackUser.tenant_id == Message.tenant_id,
                SlackUser.slack_user_id == Message.slack_user_id,
            ))
            .outerjoin(Bot, Bot.id == Message.bot_id)
            .where(Message.tenant_id == tenant.id)
            .order_by(Message.created_at.desc())
            .limit(PAGE_SIZE)
            .offset(offset)
        )
        rows = (await session.execute(stmt)).all()

        history = []
        for msg, user, bot in rows:
            history.append({
                "timestamp": msg.created_at,
                "user_name": (user.display_name or user.real_name) if user else None,
                "user_email": user.email if user else None,
                "slack_user_id": msg.slack_user_id,
                "bot_name": bot.name if bot else "—",
                "direction": msg.direction,
                "kind": msg.kind,
                "text": (msg.text or "")[:120],
            })

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return templates.TemplateResponse(
        "user_history.html",
        {
            "request": request,
            "tenant": tenant,
            "history": history,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )