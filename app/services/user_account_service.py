"""Service layer for user_accounts"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models import UserAccount

logger = logging.getLogger(__name__)


async def create_login(
    session: AsyncSession,
    *,
    tenant_id: int,
    slack_user_id: str,
    username: str,
    password: str,
) -> UserAccount:
    username = username.strip()
    acct = UserAccount(
        tenant_id=tenant_id,
        slack_user_id=slack_user_id,
        username=username,
        password_hash=hash_password(password),
        is_active=True,
    )
    session.add(acct)
    await session.flush()
    logger.info("Created user login %s for slack_user=%s", username, slack_user_id)
    return acct


async def get_login_for_user(
    session: AsyncSession, *, tenant_id: int, slack_user_id: str
) -> UserAccount | None:
    return (await session.execute(
        select(UserAccount).where(
            UserAccount.tenant_id == tenant_id,
            UserAccount.slack_user_id == slack_user_id,
        )
    )).scalar_one_or_none()


async def authenticate(
    session: AsyncSession, *, username: str, password: str
) -> UserAccount | None:
    acct = (await session.execute(
        select(UserAccount).where(UserAccount.username == username.strip())
    )).scalar_one_or_none()
    if not acct or not acct.is_active:
        return None
    if not verify_password(password, acct.password_hash):
        return None
    return acct


async def reset_password(
    session: AsyncSession, *, account_id: int, new_password: str
) -> UserAccount | None:
    acct = await session.get(UserAccount, account_id)
    if not acct:
        return None
    acct.password_hash = hash_password(new_password)
    await session.flush()
    return acct