"""Slack App Template — a reusable"""

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SlackAppTemplate(Base, TimestampMixin):
    __tablename__ = "slack_app_templates"

    id: Mapped[int] = mapped_column(primary_key=True)

    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Slack app credentials 
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    client_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    signing_secret: Mapped[str] = mapped_column(String(255), nullable=False)

    # Scopes requested during OAuth, stored as JSON list of strings
    default_scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<SlackAppTemplate {self.slug}>"