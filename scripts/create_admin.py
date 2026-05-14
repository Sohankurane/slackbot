"""Create or update an admin user from env vars (or args)."""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select

from app.core.db import get_system_sessionmaker
from app.core.logging_setup import setup_logging
from app.core.security import hash_password
from app.models import AdminUser

logger = logging.getLogger(__name__)


async def main() -> int:
    setup_logging()

    username = os.environ.get("ADMIN_DEFAULT_USERNAME")
    password = os.environ.get("ADMIN_DEFAULT_PASSWORD")

    if not username or not password:
        print("Set ADMIN_DEFAULT_USERNAME and ADMIN_DEFAULT_PASSWORD in .env")
        return 1

    sm = get_system_sessionmaker()
    async with sm() as session:
        existing = (await session.execute(
            select(AdminUser).where(AdminUser.username == username)
        )).scalar_one_or_none()

        if existing:
            existing.password_hash = hash_password(password)
            existing.is_active = True
            await session.commit()
            print(f"Updated admin '{username}' (password reset).")
        else:
            admin = AdminUser(
                username=username,
                password_hash=hash_password(password),
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            print(f"Created admin '{username}'.")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))