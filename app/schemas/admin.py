"""Request/response schemas for admin endpoints."""

from typing import Literal
from pydantic import BaseModel, Field


# --- Message sending (existing) ---

class SendAlertRequest(BaseModel):
    bot_slug: str
    channel: str = Field(..., description="Slack channel id e.g. C0XXXXX or #general")
    message: str
    level: Literal["info", "warning", "critical"] = "info"


class SendQARequest(BaseModel):
    bot_slug: str
    channel: str
    question: str


class SendMCQRequest(BaseModel):
    bot_slug: str
    channel: str
    question: str
    options: list[str] = Field(..., min_length=2, max_length=6)


# --- Tenant CRUD ---

class TenantCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    slack_team_id: str = Field(..., min_length=1, max_length=32)


class TenantUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    access_control_enabled: bool | None = None

# --- Bot CRUD ---

class BotCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    bot_token: str = Field(..., min_length=10)
    signing_secret: str = Field(..., min_length=10)
    slack_bot_user_id: str = Field(..., min_length=1, max_length=32)
    slack_app_id: str = Field(..., min_length=1, max_length=32)


class BotUpdate(BaseModel):
    name: str | None = None
    bot_token: str | None = None
    signing_secret: str | None = None
    is_active: bool | None = None