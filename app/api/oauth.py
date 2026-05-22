"""Slack OAuth install + callback endpoints """

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.config import get_settings
from app.core.db import get_system_sessionmaker
from app.models import SlackAppTemplate
from app.services.oauth_service import (
    build_install_url,
    consume_oauth_state,
    create_oauth_state,
    exchange_code_for_token,
    find_active_tenant_by_team,
    find_admin_installer,
    upsert_tenant_and_bot_from_oauth,
)
from app.services.slack_client import fetch_user_profile
from app.services.user_sync_service import sync_workspace_users_for_tenant

logger = logging.getLogger(__name__)

router = APIRouter(tags=["oauth"])
templates = Jinja2Templates(directory="app/ui/templates")

def _result(request: Request, *, success: bool, message: str, **extra):
    ctx = {"request": request, "success": success, "message": message}
    ctx.update(extra)
    status = 200 if success else 400
    return templates.TemplateResponse("oauth_result.html", ctx, status_code=status)

@router.get("/slack/install/{template_slug}/{label}")
@router.get("/slack/install/{template_slug}")
async def slack_install(request: Request, template_slug: str, label: str | None = None):
    settings = get_settings()
    if not settings.slack_oauth_redirect_uri:
        raise HTTPException(500, "OAuth redirect URI not configured")

    sm = get_system_sessionmaker()
    async with sm() as session:
        result = await session.execute(
            select(SlackAppTemplate).where(
                SlackAppTemplate.slug == template_slug,
                SlackAppTemplate.is_active.is_(True),
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(404, f"Unknown app template '{template_slug}'")

        state = await create_oauth_state(session, template_id=template.id, label=label)
        await session.commit()

    redirect_to = build_install_url(
        template=template, state=state, redirect_uri=settings.slack_oauth_redirect_uri
    )
    logger.info("OAuth install start: template=%s label=%s", template_slug, label)
    return RedirectResponse(redirect_to, status_code=302)

@router.get("/slack/oauth/callback", response_class=HTMLResponse)
async def slack_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    settings = get_settings()

    if error:
        return _result(request, success=False, message=f"Slack returned: {error}")
    if not code or not state:
        return _result(request, success=False, message="Missing code or state.")

    sm = get_system_sessionmaker()
    async with sm() as session:
        # 1. CSRF state
        captured = await consume_oauth_state(session, state=state)
        if captured is None:
            await session.commit()
            return _result(request, success=False, message="Invalid or expired state.")

        result = await session.execute(
            select(SlackAppTemplate).where(SlackAppTemplate.id == captured.app_template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            await session.commit()
            return _result(request, success=False, message="App template missing.")

        # 2. Token exchange
        payload = await exchange_code_for_token(
            template=template, code=code, redirect_uri=settings.slack_oauth_redirect_uri
        )
        if not payload.get("ok"):
            await session.commit()
            return _result(
                request, success=False,
                message=f"Token exchange failed: {payload.get('error', 'unknown')}",
            )

        team = payload.get("team", {})
        team_id = team.get("id")
        bot_token = payload.get("access_token")
        authed_user_id = (payload.get("authed_user") or {}).get("id")

        tenant = await find_active_tenant_by_team(session, team_id=team_id)
        if tenant is None:
            await session.commit()
            logger.warning("Install blocked: workspace %s not registered/active", team_id)
            return _result(
                request, success=False,
                message="Your workspace is not registered. Please contact support.",
            )

        installer_profile = await fetch_user_profile(
            bot_token=bot_token, slack_user_id=authed_user_id
        )
        installer_email = (installer_profile or {}).get("email")
        installer = await find_admin_installer(
            session, tenant_id=tenant.id, email=installer_email
        )
        if installer is None:
            await session.commit()
            logger.warning(
                "Install blocked: installer email=%s not an authorized admin for tenant=%s",
                installer_email, tenant.slug,
            )
            return _result(
                request, success=False,
                message="Your email is not authorized to install this app. "
                        "Please contact your workspace admin.",
            )

        tenant, bot = await upsert_tenant_and_bot_from_oauth(
            session, template=template, oauth_payload=payload
        )
        await session.commit()

        tenant_id = tenant.id
        tenant_slug = tenant.slug
        tenant_name = tenant.name
        bot_token_final = bot.bot_token
        bot_app_id = bot.slack_app_id
        bot_name = bot.name

    asyncio.create_task(
        sync_workspace_users_for_tenant(
            tenant_id=tenant_id, tenant_slug=tenant_slug, bot_token=bot_token_final
        )
    )

    class _T: pass
    t = _T(); t.name = tenant_name; t.slack_team_id = team_id
    b = _T(); b.name = bot_name; b.slack_app_id = bot_app_id

    logger.info("OAuth install complete: tenant=%s installer=%s", tenant_slug, installer_email)
    return _result(
        request, success=True,
        message=f"Installed in {tenant_name}", tenant=t, bot=b,
    )