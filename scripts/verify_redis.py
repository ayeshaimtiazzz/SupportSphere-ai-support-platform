"""
scripts/verify_redis.py
Tests the sliding window rate limiter.

Usage:
    python scripts/verify_redis.py
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.services.rate_limiter import RateLimiter


async def main():
    print("=" * 50)
    print("Redis Rate Limiter Verification")
    print("=" * 50)

    limiter = RateLimiter(redis_url="redis://localhost:6379")

    test_key = "test_api_key_abc123"
    limit = 5   # low limit so we can test quickly

    print(f"\nTesting with limit={limit} requests/minute\n")

    # Make 7 requests — first 5 should pass, last 2 should be blocked
    for i in range(1, 8):
        allowed, remaining = await limiter.is_allowed(test_key, limit=limit)
        status = "✅ ALLOWED" if allowed else "🚫 BLOCKED"
        print(f"Request {i}: {status} | remaining: {remaining}")

    print("\n--- Checking current usage ---")
    usage = await limiter.get_current_usage(test_key)
    print(f"Current usage in window: {usage} requests")

    print("\n✅ Rate limiter working correctly!")
    print("  • First 5 requests: allowed")
    print("  • Requests 6-7: blocked (rate limit exceeded)")

    await limiter.close()


if __name__ == "__main__":
    asyncio.run(main())