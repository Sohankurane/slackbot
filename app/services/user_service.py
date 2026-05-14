"""Service layer for SlackUser CRUD + soft delete."""

import logging
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SlackUser

logger = logging.getLogger(__name__)

async def get_or_create_user(
    session: AsyncSession,
    *,
    tenant_id: int,
    slack_user_id: str,
    profile: dict | None = None,
) -> SlackUser:
    stmt = select(SlackUser).where(
        SlackUser.tenant_id == tenant_id,
        SlackUser.slack_user_id == slack_user_id,
    )
    user = (await session.execute(stmt)).scalar_one_or_none()

    if user is None:
        user = SlackUser(
            tenant_id=tenant_id,
            slack_user_id=slack_user_id,
            display_name=(profile or {}).get("display_name"),
            real_name=(profile or {}).get("real_name"),
            email=(profile or {}).get("email"),
        )
        session.add(user)
        await session.flush()
        logger.info("Created SlackUser tenant_id=%s slack_user=%s", tenant_id, slack_user_id)
        return user

    # Auto-restore on contact
    if user.is_deleted:
        logger.info("Auto-restoring soft-deleted user %s", slack_user_id)
        user.is_deleted = False
        user.deleted_at = None

    # Update profile fields lazily 
    if profile:
        if profile.get("display_name") and profile["display_name"] != user.display_name:
            user.display_name = profile["display_name"]
        if profile.get("real_name") and profile["real_name"] != user.real_name:
            user.real_name = profile["real_name"]
        if profile.get("email") and profile["email"] != user.email:
            user.email = profile["email"]

    return user


async def soft_delete_user(session: AsyncSession, user_id: int) -> SlackUser | None:
    user = await session.get(SlackUser, user_id)
    if not user:
        return None
    user.is_deleted = True
    user.deleted_at = datetime.now(timezone.utc)
    await session.flush()
    logger.info("Soft-deleted SlackUser id=%s slack_user=%s", user.id, user.slack_user_id)
    return user


async def restore_user(session: AsyncSession, user_id: int) -> SlackUser | None:
    user = await session.get(SlackUser, user_id)
    if not user:
        return None
    user.is_deleted = False
    user.deleted_at = None
    await session.flush()
    logger.info("Restored SlackUser id=%s slack_user=%s", user.id, user.slack_user_id)
    return user


async def list_users(
    session: AsyncSession,
    *,
    tenant_id: int,
    status: Literal["active", "deleted", "all"] = "active",
) -> list[SlackUser]:
    stmt = select(SlackUser).where(SlackUser.tenant_id == tenant_id)
    if status == "active":
        stmt = stmt.where(SlackUser.is_deleted.is_(False))
    elif status == "deleted":
        stmt = stmt.where(SlackUser.is_deleted.is_(True))
    stmt = stmt.order_by(SlackUser.id.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())