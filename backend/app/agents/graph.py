"""
backend/app/agents/graph.py
Assembles the 8 nodes into a LangGraph StateGraph.

Flow:
  START
    └─► intake
          └─► language_detect
                └─► classify_intent
                      ├─► [if should_escalate] ─► escalate ─► END
                      ├─► [if tool required]   ─► tool_call ─► rag_lookup ─► resolve ─► END
                      └─► [otherwise]          ─► rag_lookup ─► resolve ─► END

Co-pilot runs as a sub-step inside escalate (when human agent is active).
"""

import logging
from langgraph.graph import StateGraph, END, START

from app.agents.state import SupportState, TOOL_REQUIRED_INTENTS
from app.agents.nodes import (
    intake_node,
    language_detect_node,
    classify_intent_node,
    rag_lookup_node,
    tool_call_node,
    co_pilot_node,
    escalate_node,
    resolve_node,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# Routing functions (conditional edges)
# These decide which node to go to next
# ─────────────────────────────────────────

def route_after_classify(state: SupportState) -> str:
    """
    After intent classification, decide next step:
    - Escalate if we've tried too many times or confidence is too low
    - Tool call if intent needs data lookup
    - RAG lookup for everything else
    """
    if state.get("should_escalate", False):
        logger.info(f"[router] → escalate (reason: {state.get('escalation_reason')})")
        return "escalate"

    intent = state.get("intent", "unknown")

    if intent in TOOL_REQUIRED_INTENTS:
        logger.info(f"[router] → tool_call (intent={intent})")
        return "tool_call"

    logger.info(f"[router] → rag_lookup (intent={intent})")
    return "rag_lookup"


def route_after_escalate(state: SupportState) -> str:
    """
    After escalation, check if co-pilot should generate suggestions.
    Always ends at END after this.
    """
    if state.get("copilot_active", False):
        logger.info("[router] → co_pilot (human agent active)")
        return "co_pilot"
    return "__end__"


def route_after_tool_call(state: SupportState) -> str:
    """After tool call, always go to RAG lookup for additional context."""
    return "rag_lookup"


# ─────────────────────────────────────────
# Build the graph
# ─────────────────────────────────────────

def build_support_graph() -> StateGraph:
    """
    Constructs and compiles the LangGraph StateGraph.
    Returns a compiled graph ready to invoke.
    """
    graph = StateGraph(SupportState)

    # ── Add all 8 nodes ──────────────────────────────────
    graph.add_node("intake", intake_node)
    graph.add_node("language_detect", language_detect_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("rag_lookup", rag_lookup_node)
    graph.add_node("tool_call", tool_call_node)
    graph.add_node("co_pilot", co_pilot_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("resolve", resolve_node)

    # ── Add edges (fixed paths) ───────────────────────────
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "language_detect")
    graph.add_edge("language_detect", "classify_intent")

    # ── Add conditional edges (routing functions) ─────────
    graph.add_conditional_edges(
        "classify_intent",
        route_after_classify,
        {
            "escalate": "escalate",
            "tool_call": "tool_call",
            "rag_lookup": "rag_lookup",
        },
    )

    graph.add_conditional_edges(
        "escalate",
        route_after_escalate,
        {
            "co_pilot": "co_pilot",
            "__end__": END,
        },
    )

    # Tool call → RAG lookup → resolve → END
    graph.add_edge("tool_call", "rag_lookup")
    graph.add_edge("rag_lookup", "resolve")
    graph.add_edge("resolve", END)
    graph.add_edge("co_pilot", END)

    # ── Compile ───────────────────────────────────────────
    compiled = graph.compile()
    logger.info("Support agent graph compiled successfully")
    return compiled


# ─────────────────────────────────────────
# Singleton graph instance
# ─────────────────────────────────────────
_graph = None


def get_graph():
    """Get or create the compiled graph (singleton)."""
    global _graph
    if _graph is None:
        _graph = build_support_graph()
    return _graph


# ─────────────────────────────────────────
# Main entry point for running the agent
# ─────────────────────────────────────────

async def run_support_agent(
    user_input: str,
    tenant_id: str,
    customer_id: str,
    conversation_id: str,
    system_prompt: str = "You are a helpful customer support agent.",
    channel: str = "web",
    copilot_active: bool = False,
) -> dict:
    """
    Run the full support agent for a single user message.

    Returns:
        dict with 'response', 'intent', 'language', 'latency_ms', 'model_used',
        'should_escalate', 'suggested_replies'
    """
    from app.agents.state import DEFAULT_STATE_VALUES

    initial_state = {
        **DEFAULT_STATE_VALUES,
        "user_input": user_input,
        "tenant_id": tenant_id,
        "customer_id": customer_id,
        "conversation_id": conversation_id,
        "system_prompt": system_prompt,
        "channel": channel,
        "copilot_active": copilot_active,
        "messages": [],
    }

    graph = get_graph()
    final_state = await graph.ainvoke(initial_state)

    return {
        "response": final_state.get("final_response", "I'm sorry, something went wrong."),
        "intent": final_state.get("intent"),
        "confidence": final_state.get("confidence", 0.0),
        "language": final_state.get("language", "en"),
        "latency_ms": final_state.get("latency_ms", 0),
        "model_used": final_state.get("model_used", "unknown"),
        "should_escalate": final_state.get("should_escalate", False),
        "suggested_replies": final_state.get("suggested_replies", []),
        "retrieved_docs_count": len(final_state.get("retrieved_docs", [])),
    }