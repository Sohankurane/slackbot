"""Scoped data for the logged-in user's own dashboard."""

import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bot, Group, GroupMember, Message, SlackUser

logger = logging.getLogger(__name__)


async def get_profile(
    session: AsyncSession, *, tenant_id: int, slack_user_id: str
) -> dict | None:
    user = (await session.execute(
        select(SlackUser).where(
            SlackUser.tenant_id == tenant_id,
            SlackUser.slack_user_id == slack_user_id,
        )
    )).scalar_one_or_none()
    if not user:
        return None
    return {
        "slack_user_id": user.slack_user_id,
        "display_name": user.display_name,
        "real_name": user.real_name,
        "email": user.email,
        "created_at": user.created_at.isoformat(),
    }


async def get_my_groups(
    session: AsyncSession, *, tenant_id: int, slack_user_id: str
) -> list[dict]:
    rows = (await session.execute(
        select(Group.name, Group.can_use_bot)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(
            Group.tenant_id == tenant_id,
            GroupMember.slack_user_id == slack_user_id,
        )
        .order_by(Group.name)
    )).all()
    return [{"name": r[0], "can_use_bot": r[1]} for r in rows]


async def get_my_messages(
    session: AsyncSession,
    *,
    tenant_id: int,
    slack_user_id: str,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    base = select(Message).where(
        Message.tenant_id == tenant_id,
        Message.slack_user_id == slack_user_id,
    )

    total = (await session.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()

    offset = (page - 1) * page_size
    rows = (await session.execute(
        base.order_by(Message.id.desc()).offset(offset).limit(page_size)
    )).scalars().all()

    # Map bot ids -> names for display
    bot_ids = {m.bot_id for m in rows if m.bot_id}
    bot_names = {}
    if bot_ids:
        bots = (await session.execute(
            select(Bot.id, Bot.name).where(Bot.id.in_(bot_ids))
        )).all()
        bot_names = {b[0]: b[1] for b in bots}

    items = [{
        "direction": m.direction,
        "kind": m.kind,
        "text": m.text,
        "bot": bot_names.get(m.bot_id, "—"),
        "created_at": m.created_at.isoformat(),
    } for m in rows]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }