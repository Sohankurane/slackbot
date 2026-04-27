"""Import every model here so Alembic autogenerate sees them."""

from app.models.base import Base, TimestampMixin
from app.models.tenant import Tenant
from app.models.bot import Bot
from app.models.slack_user import SlackUser
from app.models.message import Message

__all__ = [
    "Base",
    "TimestampMixin",
    "Tenant",
    "Bot",
    "SlackUser",
    "Message",
]