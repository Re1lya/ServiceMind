"""Redis client module."""

from functools import lru_cache

import redis

from app.core.config import settings


@lru_cache
def get_redis_client() -> redis.Redis:
    """Create a cached Redis client from REDIS_URL or host/port settings."""
    return redis.Redis.from_url(
        settings.resolved_redis_url,
        decode_responses=True,
    )
