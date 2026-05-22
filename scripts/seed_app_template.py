"""Register the existing PRJ-SK Bot as an installable App Template."""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select

from app.core.db import get_system_sessionmaker
from app.core.logging_setup import setup_logging
from app.models import SlackAppTemplate

logger = logging.getLogger(__name__)

DEFAULT_SCOPES = [
    "chat:write",
    "app_mentions:read",
    "im:history",
    "im:read",
    "im:write",
    "channels:history",
    "channels:read",
    "groups:history",
    "users:read",
    "users:read.email",
]

REQUIRED_ENV = [
    "SLACK_APP_CLIENT_ID",
    "SLACK_APP_CLIENT_SECRET",
    "SEED_SIGNING_SECRET",
]


async def main() -> int:
    setup_logging()

    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        print("Missing env vars:", ", ".join(missing))
        return 1

    sm = get_system_sessionmaker()
    async with sm() as session:
        slug = "prj-sk-bot"
        result = await session.execute(
            select(SlackAppTemplate).where(SlackAppTemplate.slug == slug)
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            template = SlackAppTemplate(
                slug=slug,
                name="PRJ-SK Bot",
                client_id=os.environ["SLACK_APP_CLIENT_ID"],
                client_secret=os.environ["SLACK_APP_CLIENT_SECRET"],
                signing_secret=os.environ["SEED_SIGNING_SECRET"],
                default_scopes=DEFAULT_SCOPES,
                is_active=True,
            )
            session.add(template)
            await session.commit()
            print(f"Created app template '{slug}'")
            print(f"Install URL: <ngrok-host>/slack/install/{slug}")
        else:
            # Refresh creds in case env changed
            existing.client_id = os.environ["SLACK_APP_CLIENT_ID"]
            existing.client_secret = os.environ["SLACK_APP_CLIENT_SECRET"]
            existing.signing_secret = os.environ["SEED_SIGNING_SECRET"]
            existing.default_scopes = DEFAULT_SCOPES
            await session.commit()
            print(f"Updated app template '{slug}'")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))