"""Slack OAuth install + callback endpoints (public — no auth required)."""

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
    upsert_tenant_and_bot_from_oauth,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["oauth"])
templates = Jinja2Templates(directory="app/ui/templates")


@router.get("/slack/install/{template_slug}/{label}")
@router.get("/slack/install/{template_slug}")
async def slack_install(
    request: Request,
    template_slug: str,
    label: str | None = None,
):
    """Public install entry point. Redirects to Slack's OAuth consent page."""
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

        state = await create_oauth_state(
            session, template_id=template.id, label=label
        )
        await session.commit()

    redirect_to = build_install_url(
        template=template,
        state=state,
        redirect_uri=settings.slack_oauth_redirect_uri,
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
    """Slack redirects users here after they click Allow (or Cancel)."""
    settings = get_settings()

    if error:
        logger.warning("OAuth callback error param: %s", error)
        return templates.TemplateResponse(
            "oauth_result.html",
            {"request": request, "success": False, "message": f"Slack returned: {error}"},
            status_code=400,
        )

    if not code or not state:
        return templates.TemplateResponse(
            "oauth_result.html",
            {"request": request, "success": False, "message": "Missing code or state."},
            status_code=400,
        )

    sm = get_system_sessionmaker()
    async with sm() as session:
        captured_state = await consume_oauth_state(session, state=state)
        if captured_state is None:
            await session.commit()
            return templates.TemplateResponse(
                "oauth_result.html",
                {"request": request, "success": False, "message": "Invalid or expired state."},
                status_code=400,
            )

        # Load the template we started with
        result = await session.execute(
            select(SlackAppTemplate).where(
                SlackAppTemplate.id == captured_state.app_template_id
            )
        )
        template = result.scalar_one_or_none()
        if not template:
            await session.commit()
            return templates.TemplateResponse(
                "oauth_result.html",
                {"request": request, "success": False, "message": "App template missing."},
                status_code=400,
            )

        payload = await exchange_code_for_token(
            template=template, code=code, redirect_uri=settings.slack_oauth_redirect_uri
        )

        if not payload.get("ok"):
            logger.error("OAuth exchange failed: %s", payload)
            await session.commit()
            return templates.TemplateResponse(
                "oauth_result.html",
                {
                    "request": request,
                    "success": False,
                    "message": f"Token exchange failed: {payload.get('error', 'unknown')}",
                },
                status_code=400,
            )

        tenant, bot = await upsert_tenant_and_bot_from_oauth(
            session, template=template, oauth_payload=payload
        )
        await session.commit()

    return templates.TemplateResponse(
        "oauth_result.html",
        {
            "request": request,
            "success": True,
            "message": f"Installed in {tenant.name}",
            "tenant": tenant,
            "bot": bot,
        },
    )