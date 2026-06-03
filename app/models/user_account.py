"""Login accounts for regular (non-admin) users."""

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserAccount(Base, TimestampMixin):
    __tablename__ = "user_accounts"
    __table_args__ = (
        Index("uq_user_account_username", "username", unique=True),
        Index("uq_user_account_slackuser", "tenant_id", "slack_user_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    slack_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<UserAccount {self.username} tenant={self.tenant_id}>"