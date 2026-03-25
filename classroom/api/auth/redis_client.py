"""Redis client + helpers for refresh tokens and rate limiting."""
import asyncio
from datetime import timedelta
from typing import Optional
import redis.asyncio as aioredis
from config import get_settings

settings = get_settings()

_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _pool


async def store_refresh_token(user_id: str, token: str) -> None:
    r = await get_redis()
    key = f"refresh:{token}"
    await r.setex(key, timedelta(days=settings.refresh_token_expire_days), user_id)


async def validate_refresh_token(token: str) -> Optional[str]:
    """Returns user_id if valid, else None."""
    r = await get_redis()
    user_id = await r.get(f"refresh:{token}")
    return user_id


async def revoke_refresh_token(token: str) -> None:
    r = await get_redis()
    await r.delete(f"refresh:{token}")


async def revoke_all_user_tokens(user_id: str) -> None:
    """Used on password reset / account deactivation."""
    r = await get_redis()
    # Scan for user's tokens (pattern search – fine for moderate scale)
    cursor = 0
    while True:
        cursor, keys = await r.scan(cursor, match="refresh:*", count=200)
        for key in keys:
            val = await r.get(key)
            if val == user_id:
                await r.delete(key)
        if cursor == 0:
            break
