"""Command handler — each bot has its own responses."""

import logging
import re
from typing import Callable, Awaitable

from app.models import Bot

logger = logging.getLogger(__name__)

_MENTION_RE = re.compile(r"^<@[UW][A-Z0-9]+>\s*")


def _normalize(text: str) -> str:
    return _MENTION_RE.sub("", text or "").strip().lower()


# --- Per-bot command tables ---
# Each entry maps a frozenset of trigger words to a response template.
# {bot_slug} in the response gets replaced with the actual bot slug.

BOT_COMMANDS: dict[str, dict[frozenset, str]] = {
    "prj-sk": {
        frozenset({"hi", "hello", "hey", "yo"}): "hello {bot_slug} here! 👋",
        frozenset({"ping"}): "pong from {bot_slug}",
        frozenset({"help"}): (
            "*PRJ-SK Bot commands:*\n"
            "• `hi` / `hello` — say hello\n"
            "• `ping` — check if I'm alive\n"
            "• `status` — system status"
        ),
        frozenset({"status"}): "✅ {bot_slug} is up and running",
    },
    "prj-sk-2": {
        frozenset({"hi", "hello", "hey", "yo"}): "hey there! {bot_slug} at your service 🤖",
        frozenset({"ping"}): "{bot_slug} pong!",
        frozenset({"help"}): (
            "*PRJ-SK Bot 2 commands:*\n"
            "• `hi` / `hello` — greet me\n"
            "• `ping` — ping me\n"
            "• `info` — about this bot"
        ),
        frozenset({"info"}): "I'm {bot_slug}, the second bot in this workspace.",
    },
    "jarvis": {
        frozenset({"hi", "hello", "hey", "yo"}): "At your service, sir. {bot_slug} online. 🛡️",
        frozenset({"ping"}): "Systems nominal — {bot_slug}.",
        frozenset({"help"}): (
            "*Jarvis commands:*\n"
            "• `hi` — initiate contact\n"
            "• `ping` — system check\n"
            "• `whoami` — workspace info\n"
            "• `report` — status report"
        ),
        frozenset({"whoami"}): "I am {bot_slug}, operating in PRJ-SK2 workspace, served by the same backend as the PRJ-SK bots.",
        frozenset({"report"}): "All systems operational. {bot_slug} standing by.",
    },
}

# Fallback used when a slug isn't in BOT_COMMANDS
_DEFAULT_COMMANDS: dict[frozenset, str] = {
    frozenset({"hi", "hello", "hey", "yo"}): "hello from {bot_slug}!",
    frozenset({"ping"}): "pong {bot_slug}",
}


def _get_commands(bot_slug: str) -> dict[frozenset, str]:
    return BOT_COMMANDS.get(bot_slug, _DEFAULT_COMMANDS)


async def handle_message(*, bot: Bot, text: str) -> str | None:
    cmd = _normalize(text)
    if not cmd:
        return None

    commands = _get_commands(bot.slug)

    for triggers, template in commands.items():
        if cmd in triggers:
            response = template.format(bot_slug=bot.slug)
            logger.info("Command matched: %r -> %r", cmd, response)
            return response

    logger.info("No command matched for %r (bot=%s)", cmd, bot.slug)
    return None