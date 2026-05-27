"""Admin JSON API — used by the UI and callable directly."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_current_admin
from app.core.db import get_system_sessionmaker
from app.models import Bot, SlackUser, Tenant
from app.schemas.admin import (
    BotCreate,
    BotUpdate,
    SendAlertRequest,
    SendMCQRequest,
    SendQARequest,
    TenantCreate,
    TenantUpdate,
)
from app.services.message_sender import send_alert, send_mcq, send_qa
from app.models import SlackUser  
from app.services.user_service import (
    list_users,
    restore_user,
    soft_delete_user,
)
from app.services.user_service import add_pending_admin
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_admin)],
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


# ---------------- Tenant CRUD ----------------

@router.get("/tenants")
async def list_tenants():
    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(select(Tenant).order_by(Tenant.id))
        tenants = result.scalars().all()
        return [
            {
                "id": t.id,
                "slug": t.slug,
                "name": t.name,
                "slack_team_id": t.slack_team_id,
                "is_active": t.is_active,
            }
            for t in tenants
        ]


@router.post("/tenants")
async def create_tenant(req: TenantCreate):
    sm = get_system_sessionmaker()
    async with sm() as session:
        tenant = Tenant(
            slug=req.slug,
            name=req.name,
            slack_team_id=req.slack_team_id,
            is_active=True,
        )
        session.add(tenant)
        try:
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail="Tenant with this slug or team_id already exists",
            ) from e
        logger.info("Created tenant %s", tenant.slug)
        return {
            "id": tenant.id,
            "slug": tenant.slug,
            "name": tenant.name,
            "slack_team_id": tenant.slack_team_id,
            "is_active": tenant.is_active,
        }


@router.patch("/tenants/{tenant_id}")
async def update_tenant(tenant_id: int, req: TenantUpdate):
    sm = get_system_sessionmaker()
    async with sm() as session:
        tenant = await session.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        if req.name is not None:
            tenant.name = req.name
        if req.is_active is not None:
            tenant.is_active = req.is_active
        await session.commit()
        logger.info("Updated tenant %s", tenant.slug)
        return {"ok": True, "id": tenant.id}


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(tenant_id: int):
    sm = get_system_sessionmaker()
    async with sm() as session:
        tenant = await session.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        await session.delete(tenant)
        await session.commit()
        logger.info("Deleted tenant id=%s", tenant_id)
        return {"ok": True}


# ---------------- Bot CRUD ----------------

@router.get("/tenants/{tenant_slug}/bots")
async def list_bots(tenant_slug: str):
    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            select(Bot, Tenant)
            .join(Tenant, Bot.tenant_id == Tenant.id)
            .where(Tenant.slug == tenant_slug)
            .order_by(Bot.id)
        )
        rows = result.all()
        return [
            {
                "id": b.id,
                "slug": b.slug,
                "name": b.name,
                "slack_app_id": b.slack_app_id,
                "slack_bot_user_id": b.slack_bot_user_id,
                "is_active": b.is_active,
                "ai_enabled": b.ai_enabled,
                "ai_system_prompt": b.ai_system_prompt,
            }
            for b, _ in rows
        ]


@router.post("/tenants/{tenant_id}/bots")
async def create_bot(tenant_id: int, req: BotCreate):
    sm = get_system_sessionmaker()
    async with sm() as session:
        tenant = await session.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        bot = Bot(
            tenant_id=tenant_id,
            slug=req.slug,
            name=req.name,
            bot_token=req.bot_token,
            signing_secret=req.signing_secret,
            slack_bot_user_id=req.slack_bot_user_id,
            slack_app_id=req.slack_app_id,
            is_active=True,
        )
        session.add(bot)
        try:
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail="A bot with this slack_bot_user_id already exists for this tenant",
            ) from e
        logger.info("Created bot %s under tenant %s", bot.slug, tenant.slug)
        return {"id": bot.id, "slug": bot.slug}


@router.patch("/bots/{bot_id}")
async def update_bot(bot_id: int, req: BotUpdate):
    sm = get_system_sessionmaker()
    async with sm() as session:
        bot = await session.get(Bot, bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        if req.name is not None:
            bot.name = req.name
        if req.bot_token is not None:
            bot.bot_token = req.bot_token
        if req.signing_secret is not None:
            bot.signing_secret = req.signing_secret
        if req.is_active is not None:
            bot.is_active = req.is_active
        await session.commit()
        logger.info("Updated bot %s", bot.slug)
        return {"ok": True, "id": bot.id}


@router.delete("/bots/{bot_id}")
async def delete_bot(bot_id: int):
    sm = get_system_sessionmaker()
    async with sm() as session:
        bot = await session.get(Bot, bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        await session.delete(bot)
        await session.commit()
        logger.info("Deleted bot id=%s", bot_id)
        return {"ok": True}


# ---------------- Message sending ----------------

@router.post("/send/alert")
async def api_send_alert(req: SendAlertRequest, tenant: str):
    bot = await _get_bot_by_slug(tenant, req.bot_slug)
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
async def api_send_qa(req: SendQARequest, tenant: str):
    bot = await _get_bot_by_slug(tenant, req.bot_slug)
    result = await send_qa(
        bot_id=bot.id,
        bot_token=bot.bot_token,
        channel=req.channel,
        question=req.question,
    )
    logger.info("Admin Q&A sent by bot=%s to channel=%s", bot.slug, req.channel)
    return {"ok": True, "ts": result.get("ts")}


@router.post("/send/mcq")
async def api_send_mcq(req: SendMCQRequest, tenant: str):
    bot = await _get_bot_by_slug(tenant, req.bot_slug)
    result = await send_mcq(
        bot_id=bot.id,
        bot_token=bot.bot_token,
        channel=req.channel,
        question=req.question,
        options=req.options,
    )
    logger.info("Admin MCQ sent by bot=%s to channel=%s", bot.slug, req.channel)
    return {"ok": True, "ts": result.get("ts")}

@router.get("/tenants/{tenant_id}/users")
async def api_list_users(tenant_id: int, status: str = "active"):
    if status not in ("active", "deleted", "all"):
        raise HTTPException(status_code=400, detail="status must be active|deleted|all")
    sm = get_system_sessionmaker()
    async with sm() as session:
        users = await list_users(session, tenant_id=tenant_id, status=status)
        return [
            {
                "id": u.id,
                "slack_user_id": u.slack_user_id,
                "display_name": u.display_name,
                "real_name": u.real_name,
                "email": u.email,
                "is_admin": u.is_admin,
                "is_deleted": u.is_deleted,
                "deleted_at": u.deleted_at.isoformat() if u.deleted_at else None,
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ]


@router.get("/users/{user_id}")
async def api_get_user(user_id: int):
    sm = get_system_sessionmaker()
    async with sm() as session:
        user = await session.get(SlackUser, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "id": user.id,
            "tenant_id": user.tenant_id,
            "slack_user_id": user.slack_user_id,
            "display_name": user.display_name,
            "real_name": user.real_name,
            "email": user.email,
            "is_deleted": user.is_deleted,
            "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
        }


@router.post("/users/{user_id}/soft-delete")
async def api_soft_delete_user(user_id: int):
    sm = get_system_sessionmaker()
    async with sm() as session:
        user = await soft_delete_user(session, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await session.commit()
        return {"ok": True, "id": user.id, "deleted_at": user.deleted_at.isoformat()}


@router.post("/users/{user_id}/restore")
async def api_restore_user(user_id: int):
    sm = get_system_sessionmaker()
    async with sm() as session:
        user = await restore_user(session, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await session.commit()
        return {"ok": True, "id": user.id}
    
@router.post("/users/{user_id}/set-admin")
async def api_set_user_admin(user_id: int, make_admin: bool = True):
    """Mark or unmark a SlackUser as an authorized installer (Requirement B1)."""
    sm = get_system_sessionmaker()
    async with sm() as session:
        user = await session.get(SlackUser, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_admin = make_admin
        await session.commit()
        logger.info(
            "User %s is_admin set to %s by admin", user.slack_user_id, make_admin
        )
        return {"ok": True, "id": user.id, "is_admin": user.is_admin}
    
@router.post("/tenants/{tenant_id}/authorize-installer")
async def api_authorize_installer(tenant_id: int, email: str):
    """Pre-authorize an email as an installer admin (Requirement B —
    works even if the person isn't a Slack user yet)."""
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    sm = get_system_sessionmaker()
    async with sm() as session:
        tenant = await session.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        user = await add_pending_admin(session, tenant_id=tenant_id, email=email)
        await session.commit()
        return {"ok": True, "id": user.id, "email": user.email}
    
class BotAIUpdate(BaseModel):
    ai_enabled: bool | None = None
    ai_system_prompt: str | None = None


@router.patch("/bots/{bot_id}/ai")
async def api_update_bot_ai(bot_id: int, req: BotAIUpdate):
    """Toggle AI on/off and set a custom system prompt for a bot."""
    sm = get_system_sessionmaker()
    async with sm() as session:
        bot = await session.get(Bot, bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        if req.ai_enabled is not None:
            bot.ai_enabled = req.ai_enabled
        if req.ai_system_prompt is not None:
            bot.ai_system_prompt = req.ai_system_prompt or None
        await session.commit()
        logger.info("Bot %s AI settings updated (enabled=%s)", bot.slug, bot.ai_enabled)
        return {
            "ok": True,
            "id": bot.id,
            "ai_enabled": bot.ai_enabled,
            "ai_system_prompt": bot.ai_system_prompt,
        }