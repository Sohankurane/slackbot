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