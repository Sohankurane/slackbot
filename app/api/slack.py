"""Slack webhook endpoint."""

import asyncio
import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.slack_verify import verify_slack_signature
from app.models import Bot, Message
from app.services.bot_router import pick_bot
from app.services.command_handler import handle_message
from app.services.slack_client import post_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["slack"])


@router.post("/events")
async def slack_events(
    request: Request,
    x_slack_signature: str = Header(default=""),
    x_slack_request_timestamp: str = Header(default=""),
):
    raw_body = await request.body()

    # Parse JSON early so we can handle url_verification before signature check
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
    from app.core.context import set_context
    from app.core.db import get_sessionmaker

    event_type = event.get("type")
    # Ignore events from bots (including ourselves) to prevent loops
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

        # Re-set context for the background task (contextvars don't auto-propagate
        # cleanly across asyncio.create_task on all Python versions)
        set_context(
            tenant_id=bot.tenant_id, tenant_slug=tenant_slug, bot_slug=bot.slug
        )

        # Log inbound
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
        if response is None:
            return

        # Send reply
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

        # Log outbound
        session.add(
            Message(
                tenant_id=bot.tenant_id,
                bot_id=bot.id,
                direction="outbound",
                kind="message",
                slack_channel_id=channel,
                slack_user_id=user,
                slack_ts=ts,
                text=response,
            )
        )
        await session.commit()
        logger.info("Replied %r in channel=%s", response, channel)