"""Seed second bot into the existing PRJ-SK tenant."""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select

from app.core.db import get_system_sessionmaker
from app.core.logging_setup import setup_logging
from app.models import Bot, Tenant

logger = logging.getLogger(__name__)

REQUIRED_ENV = [
    "SEED_TENANT_SLUG",
    "SEED2_BOT_SLUG",
    "SEED2_BOT_NAME",
    "SEED2_BOT_TOKEN",
    "SEED2_SIGNING_SECRET",
    "SEED2_BOT_USER_ID",
    "SEED2_APP_ID",
]


async def main() -> int:
    setup_logging()

    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        print("Missing env vars:", ", ".join(missing))
        return 1

    sm = get_system_sessionmaker()
    async with sm() as session:

        # Find existing tenant
        result = await session.execute(
            select(Tenant).where(Tenant.slug == os.environ["SEED_TENANT_SLUG"])
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            print(f"Tenant '{os.environ['SEED_TENANT_SLUG']}' not found. Run seed.py first.")
            return 1

        logger.info("Found tenant %s (id=%s)", tenant.slug, tenant.id)

        # Check if bot 2 already exists
        bot_user_id = os.environ["SEED2_BOT_USER_ID"]
        result = await session.execute(
            select(Bot).where(
                Bot.tenant_id == tenant.id,
                Bot.slack_bot_user_id == bot_user_id,
            )
        )
        bot = result.scalar_one_or_none()

        if bot is None:
            bot = Bot(
                tenant_id=tenant.id,
                slug=os.environ["SEED2_BOT_SLUG"],
                name=os.environ["SEED2_BOT_NAME"],
                bot_token=os.environ["SEED2_BOT_TOKEN"],
                signing_secret=os.environ["SEED2_SIGNING_SECRET"],
                slack_bot_user_id=bot_user_id,
                slack_app_id=os.environ["SEED2_APP_ID"],
                is_active=True,
            )
            session.add(bot)
            logger.info("Created bot %s for tenant %s", bot.slug, tenant.slug)
        else:
            logger.info("Bot %s already exists (id=%s)", bot.slug, bot.id)

        await session.commit()

    print("Seed bot 2 complete.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))