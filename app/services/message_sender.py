"""Send admin-triggered messages to Slack channels or users."""

import logging
from typing import Any

from app.services.slack_client import post_message

logger = logging.getLogger(__name__)


def _build_mcq_blocks(question: str, options: list[str]) -> list[dict[str, Any]]:
    """Build a Slack block kit MCQ message."""
    option_lines = "\n".join(
        f"*{chr(65 + i)}.* {opt}" for i, opt in enumerate(options)
    )
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*📋 Question*\n{question}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": option_lines,
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Reply with the letter of your answer (A, B, C...)",
                }
            ],
        },
    ]


def _build_qa_blocks(question: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*❓ Question*\n{question}",
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "Reply directly to this message with your answer."}
            ],
        },
    ]


def _build_alert_blocks(message: str, level: str = "info") -> list[dict[str, Any]]:
    icons = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
    icon = icons.get(level, "ℹ️")
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{icon} *Alert*\n{message}",
            },
        }
    ]


async def send_alert(
    *,
    bot_id: int,
    bot_token: str,
    channel: str,
    message: str,
    level: str = "info",
) -> dict[str, Any]:
    blocks = _build_alert_blocks(message, level)
    logger.info("Sending alert to channel=%s level=%s", channel, level)
    return await post_message(
        bot_id=bot_id,
        bot_token=bot_token,
        channel=channel,
        text=f"Alert: {message}",
        blocks=blocks,
    )


async def send_qa(
    *,
    bot_id: int,
    bot_token: str,
    channel: str,
    question: str,
) -> dict[str, Any]:
    blocks = _build_qa_blocks(question)
    logger.info("Sending Q&A to channel=%s", channel)
    return await post_message(
        bot_id=bot_id,
        bot_token=bot_token,
        channel=channel,
        text=question,
        blocks=blocks,
    )


async def send_mcq(
    *,
    bot_id: int,
    bot_token: str,
    channel: str,
    question: str,
    options: list[str],
) -> dict[str, Any]:
    blocks = _build_mcq_blocks(question, options)
    logger.info("Sending MCQ to channel=%s options=%s", channel, len(options))
    return await post_message(
        bot_id=bot_id,
        bot_token=bot_token,
        channel=channel,
        text=question,
        blocks=blocks,
    )