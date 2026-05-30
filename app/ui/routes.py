"""HTML UI routes — rendered with Jinja2."""

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, func, or_
from app.models import Message, SlackUser, Bot

from app.core.db import get_system_sessionmaker
from app.models import Bot, Tenant
from app.services.analytics_service import compute_dashboard_metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory="app/ui/templates")


@router.get("/admin", response_class=HTMLResponse)
async def dashboard(request: Request):

    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(select(Tenant).order_by(Tenant.id))
        tenants = list(result.scalars().all())

        # Per-tenant message counts (one grouped query)
        count_rows = (await session.execute(
            select(Message.tenant_id, func.count(Message.id), func.max(Message.created_at))
            .group_by(Message.tenant_id)
        )).all()
        counts = {tid: {"count": c, "last": last} for tid, c, last in count_rows}

        tenant_data = []
        for t in tenants:
            bots_result = await session.execute(
                select(Bot).where(Bot.tenant_id == t.id).order_by(Bot.id)
            )
            bots = list(bots_result.scalars().all())
            info = counts.get(t.id, {"count": 0, "last": None})
            tenant_data.append({
                "tenant": t,
                "bots": bots,
                "active_bots": sum(1 for b in bots if b.is_active),
                "message_count": info["count"],
                "last_active": info["last"],
            })

        metrics = await compute_dashboard_metrics(session)

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "tenant_data": tenant_data, "metrics": metrics},
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
async def user_history(
    request: Request,
    tenant_slug: str,
    page: int = 1,
    bot_id: int | None = None,
    direction: str | None = None,
    days: int | None = None,
    q: str | None = None,
):

    PAGE_SIZE = 25
    page = max(1, page)
    offset = (page - 1) * PAGE_SIZE

    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        # Bots for the filter dropdown
        bots = (await session.execute(
            select(Bot).where(Bot.tenant_id == tenant.id).order_by(Bot.id)
        )).scalars().all()

        # Build the filter conditions (shared by count + page queries)
        conditions = [Message.tenant_id == tenant.id]
        if bot_id:
            conditions.append(Message.bot_id == bot_id)
        if direction in ("inbound", "outbound"):
            conditions.append(Message.direction == direction)
        if days and days > 0:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            conditions.append(Message.created_at >= since)
        if q:
            conditions.append(Message.text.ilike(f"%{q.strip()}%"))

        # Total count with filters applied
        total = (await session.execute(
            select(func.count(Message.id)).where(and_(*conditions))
        )).scalar_one()

        # Page of joined rows
        stmt = (
            select(Message, SlackUser, Bot)
            .outerjoin(SlackUser, and_(
                SlackUser.tenant_id == Message.tenant_id,
                SlackUser.slack_user_id == Message.slack_user_id,
            ))
            .outerjoin(Bot, Bot.id == Message.bot_id)
            .where(and_(*conditions))
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

    # Build a querystring (without page) to preserve filters across pagination
    from urllib.parse import urlencode
    filter_params = {}
    if bot_id:
        filter_params["bot_id"] = bot_id
    if direction:
        filter_params["direction"] = direction
    if days:
        filter_params["days"] = days
    if q:
        filter_params["q"] = q
    filter_qs = urlencode(filter_params)

    return templates.TemplateResponse(
        "user_history.html",
        {
            "request": request,
            "tenant": tenant,
            "bots": bots,
            "history": history,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "filter_qs": filter_qs,
            "active_filters": {
                "bot_id": bot_id,
                "direction": direction,
                "days": days,
                "q": q or "",
            },
        },
    )
    
@router.get("/admin/manage/{tenant_slug}/groups", response_class=HTMLResponse)
async def manage_groups(request: Request, tenant_slug: str):
    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
    return templates.TemplateResponse(
        "manage_groups.html", {"request": request, "tenant": tenant}
    )