from fastapi import APIRouter
from pydantic import BaseModel
import os

router = APIRouter()


class HealthStatus(BaseModel):
    status: str
    postgres: str
    redis: str
    kafka: str


@router.get("/health", response_model=HealthStatus)
async def health_check():
    results = {"postgres": "unknown", "redis": "unknown", "kafka": "unknown"}

    try:
        import asyncpg
        db_url = os.getenv("DATABASE_URL", "postgresql://support_user:support_pass@localhost:5432/support_db")
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(db_url)
        await conn.execute("SELECT 1")
        await conn.close()
        results["postgres"] = "ok"
    except Exception as e:
        results["postgres"] = f"error: {str(e)[:80]}"

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        await r.ping()
        await r.aclose()
        results["redis"] = "ok"
    except Exception as e:
        results["redis"] = f"error: {str(e)[:80]}"

    try:
        import socket
        sock = socket.create_connection(("localhost", 9092), timeout=2)
        sock.close()
        results["kafka"] = "ok"
    except Exception as e:
        results["kafka"] = f"error: {str(e)[:80]}"

    overall = "healthy" if all(v == "ok" for v in results.values()) else "degraded"
    return HealthStatus(status=overall, **results)