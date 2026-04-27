"""Request/response schemas for admin endpoints."""

from typing import Literal
from pydantic import BaseModel, Field


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