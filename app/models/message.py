"""Audit log of all messages flowing through our bots."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )

    bot_id: Mapped[int | None] = mapped_column(
        ForeignKey("bots.id", ondelete="SET NULL"), index=True, nullable=True
    )

    # 'inbound' = user -> bot, 'outbound' = bot -> user/channel
    direction: Mapped[str] = mapped_column(String(16), nullable=False)

    # 'message', 'mention', 'command', 'admin_qa', 'admin_mcq', 'admin_alert'
    kind: Mapped[str] = mapped_column(String(32), nullable=False)

    slack_channel_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    slack_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    slack_ts: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )  # for dedupe / threading

    text: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Message {self.direction} {self.kind} tenant_id={self.tenant_id}>"