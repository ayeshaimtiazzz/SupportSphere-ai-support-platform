"""
backend/app/database.py
Async PostgreSQL connection pool using asyncpg.
All DB access in the app goes through this module.
"""

import asyncpg
import logging
import os
from typing import Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Global connection pool — created once on startup
_pool: Optional[asyncpg.Pool] = None


async def create_pool() -> asyncpg.Pool:
    """Create the global connection pool. Called once on app startup."""
    global _pool
    db_url = os.getenv("DATABASE_URL", "postgresql://support_user:support_pass@localhost:5432/support_db")
    # asyncpg uses postgresql:// not postgresql+asyncpg://
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    _pool = await asyncpg.create_pool(
        dsn=db_url,
        min_size=2,
        max_size=10,
        command_timeout=60,
    )
    logger.info("PostgreSQL connection pool created")
    return _pool


async def close_pool():
    """Close the pool on app shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        logger.info("PostgreSQL connection pool closed")


def get_pool() -> asyncpg.Pool:
    """Get the global pool. Raises if not initialized."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call create_pool() first.")
    return _pool


@asynccontextmanager
async def get_connection(tenant_id: Optional[str] = None):
    """
    Async context manager that yields a DB connection.
    If tenant_id is provided, sets the RLS session variable
    so Row Level Security policies apply automatically.

    Usage:
        async with get_connection(tenant_id=tenant_id) as conn:
            rows = await conn.fetch("SELECT * FROM conversations")
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        if tenant_id:
            # This makes RLS policies kick in — one tenant cannot see another's data
            await conn.execute(
                f"SET LOCAL app.current_tenant_id = '{tenant_id}'"
            )
        yield conn


# ─────────────────────────────────────────
# Helper query functions
# ─────────────────────────────────────────

async def get_tenant_by_api_key(api_key: str) -> Optional[dict]:
    """Look up tenant by API key. Returns None if not found."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, system_prompt, plan, rate_limit, is_active
            FROM tenants
            WHERE api_key = $1 AND is_active = TRUE
            """,
            api_key,
        )
    return dict(row) if row else None


async def get_or_create_customer(
    tenant_id: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
    phone: Optional[str] = None,
    channel: str = "web",
) -> dict:
    """Get existing customer or create new one."""
    async with get_connection(tenant_id=tenant_id) as conn:
        if email:
            row = await conn.fetchrow(
                "SELECT * FROM customers WHERE tenant_id = $1 AND email = $2",
                tenant_id, email,
            )
            if row:
                return dict(row)

        # Create new customer
        row = await conn.fetchrow(
            """
            INSERT INTO customers (tenant_id, name, email, phone)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            tenant_id, name or "Anonymous", email, phone,
        )
        return dict(row)


async def create_conversation(
    tenant_id: str,
    customer_id: str,
    channel: str = "web",
) -> dict:
    """Create a new conversation record."""
    async with get_connection(tenant_id=tenant_id) as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO conversations (tenant_id, customer_id, channel, status)
            VALUES ($1, $2, $3, 'open')
            RETURNING *
            """,
            tenant_id, customer_id, channel,
        )
        return dict(row)


async def save_message(
    conversation_id: str,
    role: str,
    content: str,
    tool_used: Optional[str] = None,
    tokens_input: int = 0,
    tokens_output: int = 0,
    model_used: Optional[str] = None,
    latency_ms: Optional[int] = None,
) -> dict:
    """Save a message to the messages table."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO messages
                (conversation_id, role, content, tool_used, tokens_input, tokens_output, model_used, latency_ms)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            conversation_id, role, content, tool_used,
            tokens_input, tokens_output, model_used, latency_ms,
        )
        return dict(row)


async def get_conversation_history(conversation_id: str, limit: int = 20) -> list[dict]:
    """Get recent messages for a conversation (for LLM context)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content, created_at
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            conversation_id, limit,
        )
    return [dict(r) for r in reversed(rows)]  # chronological order


async def update_conversation_status(
    conversation_id: str,
    status: str,
    intent: Optional[str] = None,
    escalation_reason: Optional[str] = None,
) -> None:
    """Update conversation status and optional fields."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE conversations
            SET status = $1,
                intent = COALESCE($2, intent),
                escalation_reason = COALESCE($3, escalation_reason),
                resolved_at = CASE WHEN $1 = 'resolved' THEN NOW() ELSE resolved_at END,
                updated_at = NOW()
            WHERE id = $4
            """,
            status, intent, escalation_reason, conversation_id,
        )


async def search_knowledge_base(
    tenant_id: str,
    embedding: list[float],
    limit: int = 5,
) -> list[dict]:
    """
    Vector similarity search in the knowledge base.
    Uses pgvector cosine similarity.
    Returns top-k most similar chunks.
    """
    async with get_connection(tenant_id=tenant_id) as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, content, metadata,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM knowledge_base
            WHERE tenant_id = $2
              AND is_active = TRUE
              AND embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $3
            """,
            embedding, tenant_id, limit,
        )
    return [dict(r) for r in rows]