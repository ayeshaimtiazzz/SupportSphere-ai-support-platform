"""
backend/app/api/conversations.py
REST API endpoints for the support chat.
"""

import uuid
import logging
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional

from app.agents.graph import run_support_agent
from app.services.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────

class MessageRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None   # None = start new conversation
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    channel: str = "web"


class MessageResponse(BaseModel):
    conversation_id: str
    response: str
    intent: Optional[str]
    confidence: float
    language: str
    latency_ms: int
    model_used: str
    should_escalate: bool
    suggested_replies: list[str]


# ─────────────────────────────────────────
# Dependency: resolve tenant from API key
# ─────────────────────────────────────────

async def get_tenant(x_api_key: str = Header(..., alias="X-API-Key")) -> dict:
    """Validates API key and returns tenant info."""
    try:
        from app.database import get_tenant_by_api_key
        tenant = await get_tenant_by_api_key(x_api_key)
    except Exception:
        # DB not ready yet — use demo tenant for development
        logger.warning("DB not available, using demo tenant")
        tenant = None

    if not tenant:
        # Development fallback: accept test keys
        if x_api_key in ("acme_test_key_abc123", "techstart_test_key_xyz789"):
            tenant = {
                "id": "a0000000-0000-0000-0000-000000000001" if "acme" in x_api_key else "b0000000-0000-0000-0000-000000000002",
                "name": "Acme Corp" if "acme" in x_api_key else "TechStart Ltd",
                "system_prompt": "You are a helpful customer support agent. Be concise and friendly.",
                "plan": "pro",
                "rate_limit": 200,
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid API key")

    return tenant


# ─────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────

@router.post("/", response_model=MessageResponse)
async def send_message(
    body: MessageRequest,
    tenant: dict = Depends(get_tenant),
):
    """
    Main endpoint: send a message and get an AI response.

    Headers required:
        X-API-Key: your tenant API key

    Example:
        POST /api/v1/conversations/
        X-API-Key: acme_test_key_abc123
        {"message": "Where is my order?"}
    """
    # Rate limiting
    allowed, remaining = await rate_limiter.is_allowed(
        api_key=tenant["id"],
        limit=tenant.get("rate_limit", 100),
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait before sending another message.",
        )

    # Use existing or create new conversation ID
    conversation_id = body.conversation_id or str(uuid.uuid4())
    customer_id = str(uuid.uuid4())  # Phase 2: resolve from DB using email

    # Try to get/create customer from DB
    try:
        from app.database import get_or_create_customer, create_conversation, save_message
        customer = await get_or_create_customer(
            tenant_id=tenant["id"],
            email=body.customer_email,
            name=body.customer_name,
            channel=body.channel,
        )
        customer_id = str(customer["id"])

        # Create conversation record if new
        if not body.conversation_id:
            conv = await create_conversation(
                tenant_id=tenant["id"],
                customer_id=customer_id,
                channel=body.channel,
            )
            conversation_id = str(conv["id"])

        # Save user message to DB
        await save_message(
            conversation_id=conversation_id,
            role="user",
            content=body.message,
        )
    except Exception as e:
        logger.warning(f"DB operations skipped (not ready): {e}")

    # Run the agent
    try:
        result = await run_support_agent(
            user_input=body.message,
            tenant_id=tenant["id"],
            customer_id=customer_id,
            conversation_id=conversation_id,
            system_prompt=tenant.get("system_prompt", "You are a helpful support agent."),
            channel=body.channel,
        )
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    return MessageResponse(
        conversation_id=conversation_id,
        response=result["response"],
        intent=result["intent"],
        confidence=result["confidence"],
        language=result["language"],
        latency_ms=result["latency_ms"],
        model_used=result["model_used"],
        should_escalate=result["should_escalate"],
        suggested_replies=result["suggested_replies"],
    )


@router.get("/{conversation_id}/history")
async def get_history(
    conversation_id: str,
    tenant: dict = Depends(get_tenant),
):
    """Get conversation message history."""
    try:
        from app.database import get_conversation_history
        history = await get_conversation_history(conversation_id, limit=50)
        return {"conversation_id": conversation_id, "messages": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))