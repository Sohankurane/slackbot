"""Per-request context (tenant + bot) using contextvars."""

from contextvars import ContextVar
from typing import Optional

current_tenant_slug: ContextVar[Optional[str]] = ContextVar(
    "current_tenant_slug", default=None
)
current_bot_slug: ContextVar[Optional[str]] = ContextVar(
    "current_bot_slug", default=None
)
current_tenant_id: ContextVar[Optional[int]] = ContextVar(
    "current_tenant_id", default=None
)


def set_context(*, tenant_id: int, tenant_slug: str, bot_slug: str | None = None) -> None:
    current_tenant_id.set(tenant_id)
    current_tenant_slug.set(tenant_slug)
    if bot_slug is not None:
        current_bot_slug.set(bot_slug)


def clear_context() -> None:
    current_tenant_id.set(None)
    current_tenant_slug.set(None)
    current_bot_slug.set(None)