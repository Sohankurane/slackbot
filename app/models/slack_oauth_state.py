"""OAuth state — short-lived random token to prevent CSRF on OAuth callback."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SlackOAuthState(Base, TimestampMixin):
    __tablename__ = "slack_oauth_states"

    id: Mapped[int] = mapped_column(primary_key=True)

    state: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    app_template_id: Mapped[int] = mapped_column(
        ForeignKey("slack_app_templates.id", ondelete="CASCADE"), nullable=False
    )

    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:
        return f"<SlackOAuthState {self.state[:8]}...>"