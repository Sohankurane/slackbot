"""User dashboard — page + scoped JSON endpoints. User session only."""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.user_deps import get_current_user_account
from app.core.db import get_system_sessionmaker
from app.models import UserAccount
from app.services.user_dashboard_service import (
    get_my_groups, get_my_messages, get_profile,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["user-dashboard"])
templates = Jinja2Templates(directory="app/ui/templates")


@router.get("/user/dashboard", response_class=HTMLResponse)
async def user_dashboard_page(request: Request):
    # The guard in main.py already ensures a user session exists.
    username = request.session.get("user_username", "")
    return templates.TemplateResponse(
        "user_dashboard.html", {"request": request, "username": username}
    )


@router.get("/api/user/me")
async def api_user_me(acct: UserAccount = Depends(get_current_user_account)):
    sm = get_system_sessionmaker()
    async with sm() as session:
        profile = await get_profile(
            session, tenant_id=acct.tenant_id, slack_user_id=acct.slack_user_id
        )
        groups = await get_my_groups(
            session, tenant_id=acct.tenant_id, slack_user_id=acct.slack_user_id
        )
    return {"username": acct.username, "profile": profile, "groups": groups}


@router.get("/api/user/messages")
async def api_user_messages(
    page: int = 1,
    acct: UserAccount = Depends(get_current_user_account),
):
    if page < 1:
        page = 1
    sm = get_system_sessionmaker()
    async with sm() as session:
        return await get_my_messages(
            session,
            tenant_id=acct.tenant_id,
            slack_user_id=acct.slack_user_id,
            page=page,
            page_size=20,
        )