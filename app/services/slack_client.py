"""Wrapper around slack_sdk.AsyncWebClient."""

import logging
from typing import Any

from slack_sdk.web.async_client import AsyncWebClient

logger = logging.getLogger(__name__)

_clients: dict[int, AsyncWebClient] = {}


def get_slack_client(bot_id: int, bot_token: str) -> AsyncWebClient:
    if bot_id not in _clients:
        _clients[bot_id] = AsyncWebClient(token=bot_token)
    return _clients[bot_id]


async def post_message(
    *,
    bot_id: int,
    bot_token: str,
    channel: str,
    text: str,
    thread_ts: str | None = None,
    blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Send a message via chat.postMessage. Returns Slack's response."""
    client = get_slack_client(bot_id, bot_token)
    kwargs: dict[str, Any] = {"channel": channel, "text": text}
    if thread_ts:
        kwargs["thread_ts"] = thread_ts
    if blocks:
        kwargs["blocks"] = blocks

    resp = await client.chat_postMessage(**kwargs)
    if not resp.get("ok"):
        logger.error("Slack postMessage failed: %s", resp)
    return resp.data if hasattr(resp, "data") else dict(resp)

async def fetch_user_profile(*, bot_token: str, slack_user_id: str) -> dict | None:
    """Call Slack's users.info to get display name + email.
    Returns dict {display_name, real_name, email} or None on failure."""
    client = AsyncWebClient(token=bot_token)
    try:
        resp = await client.users_info(user=slack_user_id)
        profile = resp.get("user", {}).get("profile", {})
        return {
            "display_name": profile.get("display_name") or None,
            "real_name": profile.get("real_name") or None,
            "email": profile.get("email") or None,
        }
    except Exception as exc:
        logger.warning("users.info failed for %s: %s", slack_user_id, exc)
        return None
    
async def list_workspace_users(*, bot_token: str) -> list[dict]:
    """Fetch all users in the workspace via users.list, handling pagination.
    Returns a list of member dicts. Skips bots and deleted accounts."""
    client = get_slack_client(0, bot_token)  # bot_id 0 = ephemeral, reuse cache
    members: list[dict] = []
    cursor = None
    try:
        while True:
            resp = await client.users_list(cursor=cursor, limit=200)
            for m in resp.get("members", []):
                if m.get("is_bot") or m.get("deleted") or m.get("id") == "USLACKBOT":
                    continue
                members.append(m)
            cursor = (resp.get("response_metadata") or {}).get("next_cursor")
            if not cursor:
                break
    except Exception as exc:
        logger.warning("users.list failed: %s", exc)
    return members