"""Slack webhook endpoint."""

import asyncio
import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.slack_verify import verify_slack_signature
from app.models import Bot, Message, Tenant
from app.services.bot_router import pick_bot
from app.services.command_handler import handle_message
from app.services.slack_client import post_message

from app.services.slack_client import fetch_user_profile
from sqlalchemy import select as _select
from app.models import SlackUser
from app.services.ai_service import generate_ai_reply

from app.core.context import set_context
from app.core.db import get_sessionmaker
from app.services.user_service import get_or_create_user
from app.services.group_service import is_user_authorized

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["slack"])

@router.post("/events")
async def slack_events(
    request: Request,
    x_slack_signature: str = Header(default=""),
    x_slack_request_timestamp: str = Header(default=""),
):
    raw_body = await request.body()

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid_json")

    if payload.get("type") == "url_verification":
        logger.info("Slack URL verification challenge received")
        return {"challenge": payload.get("challenge")}

    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        logger.warning("Slack event arrived with no tenant resolved")
        raise HTTPException(status_code=404, detail="tenant_not_found")

    from app.core.db import get_sessionmaker  # local import: avoid cycles
    tenant_slug = request.state.tenant_slug
    sm = get_sessionmaker(tenant_slug)

    async with sm() as session:
        bot = await pick_bot(session, tenant_id=tenant_id, event_envelope=payload)
        if not bot:
            logger.error("No active bot for tenant_id=%s", tenant_id)
            raise HTTPException(status_code=404, detail="no_active_bot")

        ok = verify_slack_signature(
            signing_secret=bot.signing_secret,
            request_body=raw_body,
            timestamp=x_slack_request_timestamp,
            signature=x_slack_signature,
        )
        if not ok:
            logger.warning("Slack signature verification failed for bot=%s", bot.slug)
            raise HTTPException(status_code=401, detail="bad_signature")

        event = payload.get("event", {})
        # Run handling in background so we ACK Slack within 3s
        asyncio.create_task(_handle_event(bot_id=bot.id, tenant_slug=tenant_slug, event=event))

    return {"ok": True}

async def _handle_event(*, bot_id: int, tenant_slug: str, event: dict) -> None:
    """Runs after we've already 200'd back to Slack."""
    event_type = event.get("type")
    if event.get("bot_id") or event.get("subtype") == "bot_message":
        return

    text = event.get("text", "")
    channel = event.get("channel")
    user = event.get("user")
    ts = event.get("ts")

    sm = get_sessionmaker(tenant_slug)
    async with sm() as session:
        bot = await session.get(Bot, bot_id)
        if not bot:
            logger.error("Bot %s vanished mid-handle", bot_id)
            return

        set_context(
            tenant_id=bot.tenant_id, tenant_slug=tenant_slug, bot_slug=bot.slug
        )

        # Map the Slack user
        user_display = user  # fallback to slack id
        if user:
            existing = (await session.execute(
                _select(SlackUser).where(
                    SlackUser.tenant_id == bot.tenant_id,
                    SlackUser.slack_user_id == user,
                )
            )).scalar_one_or_none()

            profile = None
            if existing is None or not existing.real_name:
                profile = await fetch_user_profile(
                    bot_token=bot.bot_token, slack_user_id=user
                )

            mapped_user = await get_or_create_user(
                session, tenant_id=bot.tenant_id, slack_user_id=user, profile=profile
            )
            user_display = (
                mapped_user.real_name
                or mapped_user.display_name
                or mapped_user.slack_user_id
            )
            logger.info(
                "From user: %s (slack_id=%s)", user_display, mapped_user.slack_user_id
            )

        # Access control — if enabled for this tenant, only members of
        # bot-enabled groups may use the bot.
        tenant = await session.get(Tenant, bot.tenant_id)
        if tenant and tenant.access_control_enabled and user:
            authorized = await is_user_authorized(
                session, tenant_id=bot.tenant_id, slack_user_id=user
            )
            if not authorized:
                logger.info(
                    "Blocked unauthorized user %s in tenant %s", user, tenant.slug
                )
                # Log the inbound attempt for the audit trail
                session.add(Message(
                    tenant_id=bot.tenant_id, bot_id=bot.id,
                    direction="inbound", kind="message",
                    slack_channel_id=channel, slack_user_id=user,
                    slack_ts=ts, text=text,
                ))
                await session.commit()
                try:
                    await post_message(
                        bot_id=bot.id, bot_token=bot.bot_token,
                        channel=channel,
                        text="You are not authorized to use this bot.",
                    )
                except Exception:
                    logger.exception("Failed to send unauthorized notice")
                return

        session.add(
            Message(
                tenant_id=bot.tenant_id,
                bot_id=bot.id,
                direction="inbound",
                kind="mention" if event_type == "app_mention" else "message",
                slack_channel_id=channel,
                slack_user_id=user,
                slack_ts=ts,
                text=text,
            )
        )
        await session.commit()

        # Get response from command handler
        response = await handle_message(bot=bot, text=text)

        # AI fallback — only if no command matched AND this bot has AI enabled
        used_ai = False
        if response is None and getattr(bot, "ai_enabled", False) and user:
            response = await generate_ai_reply(
                session, bot=bot, slack_user_id=user, user_message=text
            )
            used_ai = response is not None
            if used_ai:
                await session.commit()  # persist the AI conversation turns

        if response is None:
            return

        try:
            await post_message(
                bot_id=bot.id,
                bot_token=bot.bot_token,
                channel=channel,
                text=response,
            )
        except Exception:
            logger.exception("Failed to post Slack message")
            return

        if user and channel and not channel.startswith("D"):
            try:
                from app.services.slack_client import post_dm
                await post_dm(
                    bot_id=bot.id,
                    bot_token=bot.bot_token,
                    slack_user_id=user,
                    text=response,
                )
                logger.info("Also delivered reply to DM of user %s", user)
            except Exception:
                logger.exception("Failed to deliver DM copy")

        session.add(
            Message(
                tenant_id=bot.tenant_id,
                bot_id=bot.id,
                direction="outbound",
                kind="ai_reply" if used_ai else "message",
                slack_channel_id=channel,
                slack_user_id=user,
                slack_ts=ts,
                text=response,
            )
        )
        await session.commit()
        logger.info(
            "Replied %r to %s in channel=%s", response, user_display, channel
        )