"""Seed script — creates the first tenant + first bot."""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()  # reads .env from current working directory

from sqlalchemy import select

from app.core.db import get_system_sessionmaker
from app.core.logging_setup import setup_logging
from app.models import Bot, Tenant

# Seed default admin user
from app.models import AdminUser
from app.core.security import hash_password
from app.config import get_settings
    
logger = logging.getLogger(__name__)


REQUIRED_ENV = [
    "SEED_TENANT_SLUG",
    "SEED_TENANT_NAME",
    "SEED_SLACK_TEAM_ID",
    "SEED_BOT_SLUG",
    "SEED_BOT_NAME",
    "SEED_BOT_TOKEN",
    "SEED_SIGNING_SECRET",
    "SEED_BOT_USER_ID",
    "SEED_APP_ID",
]


async def main() -> int:
    setup_logging()

    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        print("Missing env vars in .env:", ", ".join(missing))
        return 1

    sm = get_system_sessionmaker()
    async with sm() as session:
        # --- Tenant ---
        tenant_slug = os.environ["SEED_TENANT_SLUG"]
        team_id = os.environ["SEED_SLACK_TEAM_ID"]

        result = await session.execute(
            select(Tenant).where(Tenant.slack_team_id == team_id)
        )
        tenant = result.scalar_one_or_none()

        if tenant is None:
            tenant = Tenant(
                slug=tenant_slug,
                name=os.environ["SEED_TENANT_NAME"],
                slack_team_id=team_id,
                is_active=True,
            )
            session.add(tenant)
            await session.flush()
            logger.info("Created tenant %s (id=%s)", tenant.slug, tenant.id)
        else:
            logger.info("Tenant %s already exists (id=%s)", tenant.slug, tenant.id)

        # --- Bot ---
        bot_user_id = os.environ["SEED_BOT_USER_ID"]
        result = await session.execute(
            select(Bot).where(
                Bot.tenant_id == tenant.id, Bot.slack_bot_user_id == bot_user_id
            )
        )
        bot = result.scalar_one_or_none()

        if bot is None:
            bot = Bot(
                tenant_id=tenant.id,
                slug=os.environ["SEED_BOT_SLUG"],
                name=os.environ["SEED_BOT_NAME"],
                bot_token=os.environ["SEED_BOT_TOKEN"],
                signing_secret=os.environ["SEED_SIGNING_SECRET"],
                slack_bot_user_id=bot_user_id,
                slack_app_id=os.environ["SEED_APP_ID"],
                is_active=True,
            )
            session.add(bot)
            logger.info("Created bot %s for tenant %s", bot.slug, tenant.slug)
        else:
            logger.info("Bot %s already exists (id=%s)", bot.slug, bot.id)

        await session.commit()
        settings = get_settings()
    async with sm() as session:
        result = await session.execute(
            select(AdminUser).where(AdminUser.username == settings.admin_default_username)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            admin = AdminUser(
                username=settings.admin_default_username,
                password_hash=hash_password(settings.admin_default_password),
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            logger.info("Created default admin user '%s'", admin.username)
            print(f"Default admin: username='{admin.username}' password='{settings.admin_default_password}'")
        else:
            logger.info("Admin user '%s' already exists", existing.username)

    print("Seed complete.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))