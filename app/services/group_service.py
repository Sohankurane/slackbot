"""Service layer for groups + membership + authorization checks."""

import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Group, GroupMember

logger = logging.getLogger(__name__)

async def list_groups(session: AsyncSession, *, tenant_id: int) -> list[dict]:
    groups = (await session.execute(
        select(Group).where(Group.tenant_id == tenant_id).order_by(Group.name)
    )).scalars().all()

    result = []
    for g in groups:
        count = (await session.execute(
            select(func.count(GroupMember.id)).where(GroupMember.group_id == g.id)
        )).scalar_one()
        result.append({
            "id": g.id,
            "name": g.name,
            "can_use_bot": g.can_use_bot,
            "member_count": count,
        })
    return result


async def create_group(
    session: AsyncSession, *, tenant_id: int, name: str, can_use_bot: bool = True
) -> Group:
    group = Group(tenant_id=tenant_id, name=name.strip(), can_use_bot=can_use_bot)
    session.add(group)
    await session.flush()
    logger.info("Created group %s for tenant %s", name, tenant_id)
    return group


async def get_group_members(session: AsyncSession, *, group_id: int) -> list[str]:
    rows = (await session.execute(
        select(GroupMember.slack_user_id).where(GroupMember.group_id == group_id)
    )).all()
    return [r[0] for r in rows]


async def add_member(
    session: AsyncSession, *, group_id: int, slack_user_id: str
) -> None:
    existing = (await session.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.slack_user_id == slack_user_id,
        )
    )).scalar_one_or_none()
    if existing:
        return
    session.add(GroupMember(group_id=group_id, slack_user_id=slack_user_id))
    await session.flush()


async def remove_member(
    session: AsyncSession, *, group_id: int, slack_user_id: str
) -> None:
    member = (await session.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.slack_user_id == slack_user_id,
        )
    )).scalar_one_or_none()
    if member:
        await session.delete(member)
        await session.flush()


async def is_user_authorized(
    session: AsyncSession, *, tenant_id: int, slack_user_id: str
) -> bool:
    row = (await session.execute(
        select(GroupMember.id)
        .join(Group, Group.id == GroupMember.group_id)
        .where(
            Group.tenant_id == tenant_id,
            Group.can_use_bot.is_(True),
            GroupMember.slack_user_id == slack_user_id,
        )
        .limit(1)
    )).first()
    return row is not None