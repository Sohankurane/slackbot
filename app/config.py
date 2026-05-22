"""Application settings, loaded from .env once at startup."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    app_env: Literal["local", "staging", "prod"] = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret_key: str = Field(..., min_length=16)
    log_level: str = "INFO"

    # Database
    database_url: str = Field(..., description="postgresql+asyncpg://...")

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True

    # Admin UI
    admin_token: str = Field(..., min_length=8)
    admin_default_username: str = "admin"
    admin_default_password: str = "admin"

    # Slack OAuth (for public install)
    slack_app_client_id: str = ""
    slack_app_client_secret: str = ""
    slack_oauth_redirect_uri: str = ""
    
    # Public base URL used in install links shown to users
    public_base_url: str = ""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()