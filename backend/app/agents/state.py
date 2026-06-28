"""
backend/app/agents/state.py
The central state object that flows through every node in the LangGraph.
Every node reads from this state and returns a partial update.
LangGraph merges the updates automatically.

Think of it like a baton in a relay race — each node adds information to it.
"""

from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
import operator


class SupportState(TypedDict):
    """
    Complete state for a customer support conversation.
    All fields are optional except the ones marked as required.
    """

    # ── Core identifiers ──────────────────────────────────
    tenant_id: str                      # which company is this conversation for
    customer_id: str                    # who is the customer
    conversation_id: str                # DB record UUID
    channel: str                        # 'web' | 'whatsapp' | 'voice'

    # ── Conversation messages ─────────────────────────────
    # add_messages reducer: new messages are APPENDED, not replaced
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Current user input ────────────────────────────────
    user_input: str                     # the raw message text
    language: str                       # 'en' | 'ur' (detected by language_detect_node)

    # ── Classification ────────────────────────────────────
    intent: Optional[str]               # classified intent category
    confidence: float                   # classification confidence 0.0-1.0
    attempt_count: int                  # how many classification attempts made

    # ── RAG retrieval ─────────────────────────────────────
    retrieved_docs: list[dict]          # top-k knowledge base chunks
    rag_context: str                    # formatted string of retrieved docs for LLM

    # ── Tool calling ──────────────────────────────────────
    tool_results: dict                  # results from tool calls (order lookup, etc.)
    tool_name: Optional[str]            # which tool was last called

    # ── Agent co-pilot ────────────────────────────────────
    suggested_replies: list[str]        # AI suggestions for human agents
    copilot_active: bool                # whether a human agent is viewing this

    # ── Escalation ────────────────────────────────────────
    should_escalate: bool               # flag set by classify or resolve nodes
    escalation_reason: Optional[str]    # why it was escalated

    # ── Response ──────────────────────────────────────────
    final_response: Optional[str]       # the response to send back to the customer
    model_used: str                     # which LLM generated the response
    latency_ms: int                     # how long the LLM took

    # ── Lifecycle ─────────────────────────────────────────
    is_resolved: bool                   # conversation marked as done
    csat_requested: bool                # whether CSAT survey was sent
    error: Optional[str]                # error message if something went wrong

    # ── Tenant config (loaded once at intake) ─────────────
    system_prompt: str                  # tenant's custom AI persona
    rate_limit: int                     # tenant's rate limit (for info only)


# ─────────────────────────────────────────
# Valid intent categories
# ─────────────────────────────────────────
VALID_INTENTS = [
    "order_status",
    "refund_request",
    "technical_issue",
    "billing",
    "general_faq",
    "unknown",
]

# Intents that require tool calls (data lookup)
TOOL_REQUIRED_INTENTS = {"order_status", "refund_request", "billing"}

# Default state values — used when creating a new conversation
DEFAULT_STATE_VALUES = {
    "language": "en",
    "intent": None,
    "confidence": 0.0,
    "attempt_count": 0,
    "retrieved_docs": [],
    "rag_context": "",
    "tool_results": {},
    "tool_name": None,
    "suggested_replies": [],
    "copilot_active": False,
    "should_escalate": False,
    "escalation_reason": None,
    "final_response": None,
    "model_used": "llama-3.3-70b-versatile",
    "latency_ms": 0,
    "is_resolved": False,
    "csat_requested": False,
    "error": None,
    "system_prompt": "You are a helpful customer support agent. Be concise and friendly.",
    "rate_limit": 100,
}