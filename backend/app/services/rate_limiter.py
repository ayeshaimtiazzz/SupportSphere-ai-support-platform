"""
Redis-based sliding window rate limiter.
Used to enforce per-tenant API rate limits.

How it works:
- Each tenant API key has a sorted set in Redis
- Set members = request timestamps (score = timestamp)
- On each request:
  1. Remove timestamps older than the window (1 minute)
  2. Count remaining entries
  3. If count >= limit → reject
  4. Otherwise add current timestamp → allow
- This is O(log N) and accurate — no fixed windows that reset suddenly
"""

import time
import redis.asyncio as aioredis
from typing import Optional
import os


class RateLimiter:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis = aioredis.from_url(
            redis_url or os.getenv("REDIS_URL", "redis://localhost:6379"),
            encoding="utf-8",
            decode_responses=True,
        )

    async def is_allowed(
        self,
        api_key: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """
        Check if this API key is within rate limit.

        Returns:
            (allowed: bool, remaining: int)
        """
        key = f"rate_limit:{api_key}"
        now = time.time()
        window_start = now - window_seconds

        # Pipeline: atomic execution of all 4 commands
        async with self.redis.pipeline(transaction=True) as pipe:
            # 1. Remove old timestamps outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            # 2. Count current requests in window
            pipe.zcard(key)
            # 3. Add current request
            pipe.zadd(key, {str(now): now})
            # 4. Set TTL so keys auto-clean
            pipe.expire(key, window_seconds + 1)
            results = await pipe.execute()

        current_count = results[1]  # zcard result (before adding current)

        if current_count >= limit:
            return False, 0

        remaining = limit - current_count - 1
        return True, max(0, remaining)

    async def get_current_usage(self, api_key: str, window_seconds: int = 60) -> int:
        """How many requests has this key made in the current window."""
        key = f"rate_limit:{api_key}"
        now = time.time()
        window_start = now - window_seconds
        await self.redis.zremrangebyscore(key, 0, window_start)
        return await self.redis.zcard(key)

    async def close(self):
        await self.redis.aclose()


# ─────────────────────────────────────────
# FastAPI dependency for rate limiting
# ─────────────────────────────────────────
from fastapi import HTTPException, Header, Depends
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)
rate_limiter = RateLimiter()


async def check_rate_limit(api_key: str = Depends(api_key_header)):
    """
    FastAPI dependency. Add to any route that needs rate limiting:

        @router.post("/message")
        async def send_message(
            body: MessageRequest,
            tenant = Depends(get_tenant_from_api_key),
            _ = Depends(check_rate_limit),
        ):
    """
    # In Phase 2 we'll look up the tenant's actual limit from DB
    # For now, default 100 req/min
    allowed, remaining = await rate_limiter.is_allowed(api_key, limit=100)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please wait before retrying.",
                "retry_after_seconds": 60,
            },
            headers={"X-RateLimit-Remaining": "0", "Retry-After": "60"},
        )

    return {"api_key": api_key, "remaining": remaining}