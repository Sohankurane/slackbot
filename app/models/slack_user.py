"""Slack users we've seen in any tenant.

Supports soft delete via is_deleted + deleted_at. Message history references
slack_user_id by string (not FK to this table), so soft-deleting a user
preserves their message log.

is_admin marks users authorized to install the app via OAuth (Requirement B)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, false
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SlackUser(Base, TimestampMixin):
    __tablename__ = "slack_users"
    __table_args__ = (
        Index("uq_user_per_tenant", "tenant_id", "slack_user_id", unique=True),
        Index("ix_slack_users_tenant_active", "tenant_id", "is_deleted"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )

    slack_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    real_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Authorized to install the app via OAuth (Requirement B1)
    is_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(
        default=False, server_default=false(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SlackUser {self.slack_user_id} tenant_id={self.tenant_id} admin={self.is_admin}>"