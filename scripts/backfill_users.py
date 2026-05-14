"""Backfill display_name/real_name/email for SlackUsers that don't have it yet.

For each tenant, picks an active bot to use its token, then calls
Slack's users.info for every user missing profile data."""

import asyncio
import logging
import sys

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select

from app.core.db import get_system_sessionmaker
from app.core.logging_setup import setup_logging
from app.models import Bot, SlackUser, Tenant
from app.services.slack_client import fetch_user_profile

logger = logging.getLogger(__name__)


async def main() -> int:
    setup_logging()
    sm = get_system_sessionmaker()

    async with sm() as session:
        # All tenants
        tenants = (await session.execute(select(Tenant))).scalars().all()

        for tenant in tenants:
            # Pick the first active bot for this tenant
            bot = (await session.execute(
                select(Bot).where(Bot.tenant_id == tenant.id, Bot.is_active.is_(True))
            )).scalars().first()
            if not bot:
                logger.warning("No active bot for tenant %s, skipping", tenant.slug)
                continue

            # Users missing profile info
            users = (await session.execute(
                select(SlackUser).where(
                    SlackUser.tenant_id == tenant.id,
                    SlackUser.real_name.is_(None),
                )
            )).scalars().all()

            if not users:
                logger.info("Tenant %s: nothing to backfill", tenant.slug)
                continue

            logger.info("Tenant %s: backfilling %d users", tenant.slug, len(users))
            for u in users:
                profile = await fetch_user_profile(
                    bot_token=bot.bot_token, slack_user_id=u.slack_user_id
                )
                if profile:
                    u.display_name = profile.get("display_name") or u.display_name
                    u.real_name = profile.get("real_name") or u.real_name
                    u.email = profile.get("email") or u.email
                    logger.info(
                        "  %s -> %s / %s",
                        u.slack_user_id,
                        u.real_name,
                        u.email or "no-email",
                    )

            await session.commit()

    print("Backfill complete.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))