import logging

from app.core.db import get_sessionmaker
from app.services.slack_client import list_workspace_users
from app.services.user_service import get_or_create_user

logger = logging.getLogger(__name__)

async def sync_workspace_users_for_tenant(
    *, tenant_id: int, tenant_slug: str, bot_token: str
) -> None:

    logger.info("Starting workspace user sync for tenant=%s", tenant_slug)

    members = await list_workspace_users(bot_token=bot_token)
    if not members:
        logger.info("No members returned for tenant=%s", tenant_slug)
        return

    sm = get_sessionmaker(tenant_slug)
    created_or_updated = 0

    async with sm() as session:
        for m in members:
            profile = m.get("profile", {}) or {}
            await get_or_create_user(
                session,
                tenant_id=tenant_id,
                slack_user_id=m["id"],
                profile={
                    "display_name": profile.get("display_name") or None,
                    "real_name": profile.get("real_name") or None,
                    "email": profile.get("email") or None,
                },
            )
            created_or_updated += 1
        await session.commit()

    logger.info(
        "Workspace user sync complete for tenant=%s — %d users processed",
        tenant_slug,
        created_or_updated,
    )