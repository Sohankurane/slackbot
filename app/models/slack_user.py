from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, false
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

    slack_user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    real_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(
        default=False, server_default=false(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<SlackUser {self.slack_user_id} tenant_id={self.tenant_id} deleted={self.is_deleted}>"