"""Bot = one Slack app installed in a tenant's workspace."""

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.tenant import Tenant

from app.models.base import Base, TimestampMixin


class Bot(Base, TimestampMixin):
    __tablename__ = "bots"
    __table_args__ = (
        # Each bot's slack user id must be unique within a tenant
        UniqueConstraint("tenant_id", "slack_bot_user_id", name="uq_bot_per_tenant"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Slug we use in logs
    slug: Mapped[str] = mapped_column(String(64), nullable=False)

    # Friendly display name
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Slack credentials.
    bot_token: Mapped[str] = mapped_column(String(255), nullable=False)
    signing_secret: Mapped[str] = mapped_column(String(255), nullable=False)

    # Slack's id for this bot's user account
    slack_bot_user_id: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )

    # Slack app id
    slack_app_id: Mapped[str] = mapped_column(String(32), nullable=False)

    is_active: Mapped[Boolean] = mapped_column(Boolean, default=True, nullable=False)
    # AI fallback settings
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="bots")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Bot {self.slug} tenant_id={self.tenant_id}>"