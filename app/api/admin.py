"""Admin JSON API — used by the UI and callable directly."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin_token
from app.core.db import get_system_sessionmaker
from app.models import Bot, Tenant
from app.schemas.admin import SendAlertRequest, SendMCQRequest, SendQARequest
from app.services.message_sender import send_alert, send_mcq, send_qa

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_token)],
)


async def _get_bot_by_slug(tenant_slug: str, bot_slug: str) -> Bot:
    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            select(Bot)
            .join(Tenant, Bot.tenant_id == Tenant.id)
            .where(Tenant.slug == tenant_slug, Bot.slug == bot_slug, Bot.is_active.is_(True))
        )
        bot = result.scalar_one_or_none()
        if not bot:
            raise HTTPException(status_code=404, detail=f"Bot '{bot_slug}' not found")
        return bot


@router.get("/tenants")
async def list_tenants():
    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(select(Tenant).where(Tenant.is_active.is_(True)))
        tenants = result.scalars().all()
        return [{"id": t.id, "slug": t.slug, "name": t.name} for t in tenants]


@router.get("/tenants/{tenant_slug}/bots")
async def list_bots(tenant_slug: str):
    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            select(Bot)
            .join(Tenant, Bot.tenant_id == Tenant.id)
            .where(Tenant.slug == tenant_slug, Bot.is_active.is_(True))
        )
        bots = result.scalars().all()
        return [{"id": b.id, "slug": b.slug, "name": b.name} for b in bots]


@router.post("/send/alert")
async def api_send_alert(req: SendAlertRequest, tenant_slug: str):
    bot = await _get_bot_by_slug(tenant_slug, req.bot_slug)
    result = await send_alert(
        bot_id=bot.id,
        bot_token=bot.bot_token,
        channel=req.channel,
        message=req.message,
        level=req.level,
    )
    logger.info("Admin alert sent by bot=%s to channel=%s", bot.slug, req.channel)
    return {"ok": True, "ts": result.get("ts")}


@router.post("/send/qa")
async def api_send_qa(req: SendQARequest, tenant_slug: str):
    bot = await _get_bot_by_slug(tenant_slug, req.bot_slug)
    result = await send_qa(
        bot_id=bot.id,
        bot_token=bot.bot_token,
        channel=req.channel,
        question=req.question,
    )
    logger.info("Admin Q&A sent by bot=%s to channel=%s", bot.slug, req.channel)
    return {"ok": True, "ts": result.get("ts")}


@router.post("/send/mcq")
async def api_send_mcq(req: SendMCQRequest, tenant_slug: str):
    bot = await _get_bot_by_slug(tenant_slug, req.bot_slug)
    result = await send_mcq(
        bot_id=bot.id,
        bot_token=bot.bot_token,
        channel=req.channel,
        question=req.question,
        options=req.options,
    )
    logger.info("Admin MCQ sent by bot=%s to channel=%s", bot.slug, req.channel)
    return {"ok": True, "ts": result.get("ts")}