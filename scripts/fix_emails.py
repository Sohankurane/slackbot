"""One-time script to backfill emails for existing SlackUsers."""

import asyncio
import sys

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select

from app.core.db import get_system_sessionmaker
from app.core.logging_setup import setup_logging
from app.models import Bot, SlackUser, Tenant
from app.services.slack_client import fetch_user_profile


async def main() -> int:
    setup_logging()
    sm = get_system_sessionmaker()

    async with sm() as session:
        tenants = (await session.execute(select(Tenant))).scalars().all()

        for tenant in tenants:
            bot = (await session.execute(
                select(Bot).where(Bot.tenant_id == tenant.id, Bot.is_active.is_(True))
            )).scalars().first()
            if not bot:
                print(f"[{tenant.slug}] no active bot, skipping")
                continue

            users = (await session.execute(
                select(SlackUser).where(SlackUser.tenant_id == tenant.id)
            )).scalars().all()

            for u in users:
                profile = await fetch_user_profile(
                    bot_token=bot.bot_token, slack_user_id=u.slack_user_id
                )
                if profile:
                    if profile.get("email"):
                        u.email = profile["email"]
                    if profile.get("real_name"):
                        u.real_name = profile["real_name"]
                    if profile.get("display_name"):
                        u.display_name = profile["display_name"]
                    email = profile.get("email") or "no-email"
                    print(f"[{tenant.slug}] {u.slack_user_id} -> {email}")

            await session.commit()

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))