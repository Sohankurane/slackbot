"""Dependency to resolve the current logged-in user account from session."""

from fastapi import HTTPException, Request, status

from app.core.db import get_system_sessionmaker
from app.models import UserAccount


async def get_current_user_account(request: Request) -> UserAccount:
    uid = request.session.get("user_account_id") if hasattr(request, "session") else None
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
    sm = get_system_sessionmaker()
    async with sm() as session:
        acct = await session.get(UserAccount, uid)
        if not acct or not acct.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")
        return acct