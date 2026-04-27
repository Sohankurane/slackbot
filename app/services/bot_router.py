"""Pick the right bot for an incoming Slack event."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import current_bot_slug
from app.models import Bot

logger = logging.getLogger(__name__)


async def pick_bot(
    session: AsyncSession,
    *,
    tenant_id: int,
    event_envelope: dict[str, Any],
) -> Bot | None:
    api_app_id = event_envelope.get("api_app_id")

    stmt = select(Bot).where(Bot.tenant_id == tenant_id, Bot.is_active.is_(True))
    result = await session.execute(stmt)
    bots = list(result.scalars().all())

    if not bots:
        return None

    if api_app_id:
        for b in bots:
            if b.slack_app_id == api_app_id:
                current_bot_slug.set(b.slug)
                return b

    # Fallback: first active bot
    chosen = bots[0]
    current_bot_slug.set(chosen.slug)
    if len(bots) > 1:
        logger.warning(
            "Multiple bots for tenant_id=%s, no api_app_id match; using %s",
            tenant_id,
            chosen.slug,
        )
    return chosen