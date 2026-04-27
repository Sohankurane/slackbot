"""Async Redis client. Optional — controlled by REDIS_ENABLED in .env."""

import logging
from typing import Optional

from redis.asyncio import Redis, from_url

from app.config import get_settings

logger = logging.getLogger(__name__)

_redis: Optional[Redis] = None


async def get_redis() -> Optional[Redis]:
    """Returns a connected Redis client, or None if disabled."""
    global _redis
    settings = get_settings()
    if not settings.redis_enabled:
        return None
    if _redis is None:
        _redis = from_url(settings.redis_url, decode_responses=True)
        try:
            await _redis.ping()
            logger.info("Redis connected at %s", settings.redis_url)
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — continuing without cache", exc)
            _redis = None
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")