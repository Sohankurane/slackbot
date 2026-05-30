"""AI fallback replies via Groq, with short-term conversation memory."""

import logging

from groq import AsyncGroq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import AIConversationTurn, Bot
import re

def _markdown_to_slack(text: str) -> str:
    """Convert standard markdown to Slack's mrkdwn format."""
    # **bold** → *bold*
    text = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", text)
    # __bold__ → *bold*
    text = re.sub(r"__([^_]+)__", r"*\1*", text)
    # ### Headings → *Heading*
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # [text](url) → <url|text>  (Slack link syntax)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
    # Bullet lists: "- item" stays as "- item" (Slack handles this fine)
    # Numbered lists also work as-is
    return text

logger = logging.getLogger(__name__)

_client: AsyncGroq | None = None

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful Slack assistant bot. Keep replies concise and friendly, "
    "usually 1-3 sentences. You're chatting inside Slack, so avoid long essays. "
    "If you don't know something, say so briefly. "
    "Do NOT use markdown formatting like **bold**, _italic_, or `code`. "
    "If you need emphasis, use Slack's syntax: *bold* with single asterisks, "
    "_italic_ with underscores, `code` with backticks. Plain text is usually best."
)

MAX_USER_MESSAGE_CHARS = 2000


def _get_client() -> AsyncGroq | None:
    global _client
    settings = get_settings()
    if not settings.groq_api_key:
        return None
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key)
    return _client



async def _fetch_recent_turns(
    session: AsyncSession,
    *,
    tenant_id: int,
    bot_id: int,
    slack_user_id: str,
    limit: int,
) -> list[dict]:
    """Return recent turns in chronological order as [{role, content}, ...]."""
    result = await session.execute(
        select(AIConversationTurn)
        .where(
            AIConversationTurn.tenant_id == tenant_id,
            AIConversationTurn.bot_id == bot_id,
            AIConversationTurn.slack_user_id == slack_user_id,
        )
        .order_by(AIConversationTurn.id.desc())
        .limit(limit)
    )
    turns = list(result.scalars().all())
    turns.reverse()  # chronological
    return [{"role": t.role, "content": t.content} for t in turns]


async def _save_turn(
    session: AsyncSession,
    *,
    tenant_id: int,
    bot_id: int,
    slack_user_id: str,
    role: str,
    content: str,
) -> None:
    session.add(
        AIConversationTurn(
            tenant_id=tenant_id,
            bot_id=bot_id,
            slack_user_id=slack_user_id,
            role=role,
            content=content,
        )
    )


async def _trim_old_turns(
    session: AsyncSession,
    *,
    tenant_id: int,
    bot_id: int,
    slack_user_id: str,
    keep: int,
) -> None:
    """Delete turns beyond the most recent `keep`."""
    result = await session.execute(
        select(AIConversationTurn.id)
        .where(
            AIConversationTurn.tenant_id == tenant_id,
            AIConversationTurn.bot_id == bot_id,
            AIConversationTurn.slack_user_id == slack_user_id,
        )
        .order_by(AIConversationTurn.id.desc())
        .offset(keep)
    )
    old_ids = [row[0] for row in result.all()]
    if old_ids:
        for oid in old_ids:
            obj = await session.get(AIConversationTurn, oid)
            if obj:
                await session.delete(obj)


async def generate_ai_reply(
    session: AsyncSession,
    *,
    bot: Bot,
    slack_user_id: str,
    user_message: str,
) -> str | None:
    """Generate an AI reply using Groq, with short context memory.

    Returns the reply text, or None if AI is unavailable/errors."""
    client = _get_client()
    if client is None:
        logger.warning("Groq API key not configured — AI reply skipped")
        return None

    settings = get_settings()
    user_message = (user_message or "")[:MAX_USER_MESSAGE_CHARS]

    # Build message list: system prompt + recent context + new message
    system_prompt = bot.ai_system_prompt or DEFAULT_SYSTEM_PROMPT
    history = await _fetch_recent_turns(
        session,
        tenant_id=bot.tenant_id,
        bot_id=bot.id,
        slack_user_id=slack_user_id,
        limit=settings.ai_context_turns,
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        completion = await client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            max_tokens=400,
            temperature=0.7,
            timeout=10.0,
        )
        reply = completion.choices[0].message.content.strip()
        reply = _markdown_to_slack(reply)
    except Exception:
        logger.exception("Groq AI call failed")
        return None

    if not reply:
        return None

    # Save both turns + trim
    await _save_turn(
        session,
        tenant_id=bot.tenant_id, bot_id=bot.id,
        slack_user_id=slack_user_id, role="user", content=user_message,
    )
    await _save_turn(
        session,
        tenant_id=bot.tenant_id, bot_id=bot.id,
        slack_user_id=slack_user_id, role="assistant", content=reply,
    )
    await _trim_old_turns(
        session,
        tenant_id=bot.tenant_id, bot_id=bot.id,
        slack_user_id=slack_user_id, keep=settings.ai_context_turns,
    )

    logger.info("AI reply generated (%d chars) for bot=%s", len(reply), bot.slug)
    return reply