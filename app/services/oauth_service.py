"""OAuth install logic."""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Bot, SlackAppTemplate, SlackOAuthState, Tenant
from app.utils.ids import slugify

logger = logging.getLogger(__name__)

STATE_TTL_MINUTES = 10
SLACK_OAUTH_AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
SLACK_OAUTH_ACCESS_URL = "https://slack.com/api/oauth.v2.access"


async def create_oauth_state(
    session: AsyncSession,
    *,
    template_id: int,
    label: str | None = None,
) -> str:
    state = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES)
    session.add(
        SlackOAuthState(
            state=state,
            app_template_id=template_id,
            label=label,
            expires_at=expires_at,
        )
    )
    await session.flush()
    return state


async def consume_oauth_state(
    session: AsyncSession, *, state: str
) -> SlackOAuthState | None:
    result = await session.execute(
        select(SlackOAuthState).where(SlackOAuthState.state == state)
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    now = datetime.now(timezone.utc)
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        await session.delete(row)
        return None
    # Capture data before deletion (avoid stale-object issues)
    captured = SlackOAuthState(
        state=row.state,
        app_template_id=row.app_template_id,
        label=row.label,
        expires_at=row.expires_at,
    )
    await session.delete(row)
    return captured


def build_install_url(
    *,
    template: SlackAppTemplate,
    state: str,
    redirect_uri: str,
) -> str:
    scopes = ",".join(template.default_scopes or [])
    params = {
        "client_id": template.client_id,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{SLACK_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(
    *,
    template: SlackAppTemplate,
    code: str,
    redirect_uri: str,
) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            SLACK_OAUTH_ACCESS_URL,
            data={
                "client_id": template.client_id,
                "client_secret": template.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        return resp.json()


async def upsert_tenant_and_bot_from_oauth(
    session: AsyncSession,
    *,
    template: SlackAppTemplate,
    oauth_payload: dict,
) -> tuple[Tenant, Bot]:
    team = oauth_payload.get("team", {})
    team_id = team.get("id")
    team_name = team.get("name") or team_id

    access_token = oauth_payload.get("access_token")
    bot_user_id = oauth_payload.get("bot_user_id")
    app_id = oauth_payload.get("app_id")

    if not (team_id and access_token and bot_user_id and app_id):
        raise ValueError(f"OAuth payload missing required fields: {oauth_payload}")

    # Upsert tenant
    result = await session.execute(
        select(Tenant).where(Tenant.slack_team_id == team_id)
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(
            slug=slugify(team_name) or team_id.lower(),
            name=team_name,
            slack_team_id=team_id,
            is_active=True,
        )
        session.add(tenant)
        await session.flush()
        logger.info("OAuth: created tenant %s", tenant.slug)
    else:
        tenant.is_active = True
        tenant.name = team_name
        logger.info("OAuth: reused tenant %s", tenant.slug)

    # Upsert bot 
    result = await session.execute(
        select(Bot).where(
            Bot.tenant_id == tenant.id, Bot.slack_bot_user_id == bot_user_id
        )
    )
    bot = result.scalar_one_or_none()
    if bot is None:
        bot = Bot(
            tenant_id=tenant.id,
            slug=template.slug,
            name=template.name,
            bot_token=access_token,
            signing_secret=template.signing_secret,
            slack_bot_user_id=bot_user_id,
            slack_app_id=app_id,
            is_active=True,
        )
        session.add(bot)
        logger.info("OAuth: created bot %s for tenant %s", bot.slug, tenant.slug)
    else:
        bot.bot_token = access_token
        bot.signing_secret = template.signing_secret
        bot.is_active = True
        logger.info("OAuth: refreshed bot %s for tenant %s", bot.slug, tenant.slug)

    await session.flush()
    return tenant, bot

async def find_active_tenant_by_team(
    session: AsyncSession, *, team_id: str
) -> Tenant | None:
    """Requirement A — workspace must be registered AND active."""
    result = await session.execute(
        select(Tenant).where(
            Tenant.slack_team_id == team_id,
            Tenant.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def find_admin_installer(
    session: AsyncSession, *, tenant_id: int, email: str
) -> object | None:
    """Requirement B1 — installer's email must exist in our DB,
    belong to this tenant, be marked admin, and not be soft-deleted."""
    from app.models import SlackUser

    if not email:
        return None
    result = await session.execute(
        select(SlackUser).where(
            SlackUser.tenant_id == tenant_id,
            SlackUser.email == email,
            SlackUser.is_admin.is_(True),
            SlackUser.is_deleted.is_(False),
        )
    )
    return result.scalar_one_or_none()