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