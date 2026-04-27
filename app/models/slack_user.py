"""Slack users we've seen in any tenant."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SlackUser(Base, TimestampMixin):
    __tablename__ = "slack_users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slack_user_id", name="uq_user_per_tenant"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Slack's user id
    slack_user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # We fill these in lazily when we have time to call users.info
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    real_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<SlackUser {self.slack_user_id} tenant_id={self.tenant_id}>"