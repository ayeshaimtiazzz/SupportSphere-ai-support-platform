"""
backend/app/agents/nodes.py
All 8 nodes of the support agent graph.

Node execution order (depends on routing):
  intake → language_detect → classify_intent → rag_lookup → tool_call → resolve
                                             ↘ escalate (if needed)
                                             ↘ co_pilot (if human agent assigned)

Each node:
  - Receives the full SupportState
  - Does its work
  - Returns a dict with ONLY the fields it changed (LangGraph merges this)
"""

import time
import json
import logging
import os
from typing import Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_groq import ChatGroq

from app.agents.state import SupportState, VALID_INTENTS, TOOL_REQUIRED_INTENTS, DEFAULT_STATE_VALUES
from app.services.embeddings import embed_text
from app.services import kafka_producer

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# Shared LLM client (Groq, free tier)
# ─────────────────────────────────────────
def get_llm(temperature: float = 0.3) -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=temperature,
        api_key=os.getenv("GROQ_API_KEY"),
        max_tokens=1024,
    )


# ════════════════════════════════════════════════════════════
# NODE 1: INTAKE
# Validates input, loads tenant config and customer history
# ════════════════════════════════════════════════════════════
async def intake_node(state: SupportState) -> dict:
    """
    First node. Validates the incoming message and sets up context.
    In Phase 2 we load from DB; the DB calls are wrapped in try/except
    so the graph works even before DB is connected.
    """
    logger.info(f"[intake] conv={state['conversation_id'][:8]} | input='{state['user_input'][:50]}'")

    # Publish Kafka event
    await kafka_producer.emit_message_received(
        tenant_id=state["tenant_id"],
        conversation_id=state["conversation_id"],
        content=state["user_input"],
        channel=state.get("channel", "web"),
    )

    # Add the user message to the messages list
    user_msg = HumanMessage(content=state["user_input"])

    # Try to load conversation history from DB
    history_context = ""
    try:
        from app.database import get_conversation_history
        history = await get_conversation_history(state["conversation_id"], limit=10)
        if history:
            history_context = f"Previous messages: {len(history)} exchanges in this conversation."
    except Exception as e:
        logger.warning(f"[intake] Could not load history (DB not ready?): {e}")

    return {
        "messages": [user_msg],
        "attempt_count": state.get("attempt_count", 0),
        "error": None,  # clear any previous error
    }


# ════════════════════════════════════════════════════════════
# NODE 2: LANGUAGE DETECTION
# Detects if message is English or Urdu
# ════════════════════════════════════════════════════════════
async def language_detect_node(state: SupportState) -> dict:
    """
    Detects language of the user's input.
    Currently supports: English ('en') and Urdu ('ur').
    Uses a simple LLM call — fast and accurate.
    """
    user_input = state["user_input"]

    # Quick heuristic: if it contains Urdu Unicode range, it's likely Urdu
    urdu_chars = sum(1 for c in user_input if '\u0600' <= c <= '\u06FF')
    if urdu_chars > len(user_input) * 0.3:
        logger.info("[language_detect] Detected: Urdu (heuristic)")
        return {"language": "ur"}

    # For ambiguous cases, ask the LLM
    llm = get_llm(temperature=0.0)
    prompt = f"""Detect the language of this text. Reply with ONLY 'en' for English or 'ur' for Urdu.
Text: {user_input[:200]}
Language:"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        lang = response.content.strip().lower()[:2]
        if lang not in ("en", "ur"):
            lang = "en"
    except Exception as e:
        logger.warning(f"[language_detect] LLM error, defaulting to 'en': {e}")
        lang = "en"

    logger.info(f"[language_detect] Detected: {lang}")
    return {"language": lang}


# ════════════════════════════════════════════════════════════
# NODE 3: INTENT CLASSIFICATION
# Classifies the user's intent into one of 6 categories
# ════════════════════════════════════════════════════════════
async def classify_intent_node(state: SupportState) -> dict:
    """
    Classifies user intent. Returns intent + confidence score.
    If confidence is low and we've tried 3 times → escalate.
    """
    llm = get_llm(temperature=0.0)
    attempt = state.get("attempt_count", 0) + 1

    prompt = f"""You are an intent classifier for a customer support system.
Classify the customer's message into EXACTLY ONE of these categories:
- order_status: asking about order tracking, delivery, shipment
- refund_request: asking for refund, return, money back
- technical_issue: app not working, bug, error, can't login
- billing: invoice, payment, charge, subscription
- general_faq: product info, how-to, general questions
- unknown: cannot determine intent

Customer message: "{state['user_input']}"

Respond in JSON format only:
{{"intent": "<category>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}}"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content.strip()

        # Strip markdown code fences if present
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()

        result = json.loads(raw)
        intent = result.get("intent", "unknown")
        confidence = float(result.get("confidence", 0.5))

        # Validate intent is one of our categories
        if intent not in VALID_INTENTS:
            intent = "unknown"
            confidence = 0.0

    except Exception as e:
        logger.error(f"[classify_intent] Error: {e}")
        intent = "unknown"
        confidence = 0.0

    logger.info(f"[classify_intent] intent={intent} confidence={confidence:.2f} attempt={attempt}")

    # Emit Kafka event
    await kafka_producer.emit_intent_classified(
        tenant_id=state["tenant_id"],
        conversation_id=state["conversation_id"],
        intent=intent,
        confidence=confidence,
    )

    # Should we escalate? — low confidence after 3 attempts
    should_escalate = (intent == "unknown" and attempt >= 3)

    return {
        "intent": intent,
        "confidence": confidence,
        "attempt_count": attempt,
        "should_escalate": should_escalate,
        "escalation_reason": "Could not understand intent after 3 attempts" if should_escalate else None,
    }


# ════════════════════════════════════════════════════════════
# NODE 4: RAG LOOKUP
# Embeds query and searches pgvector knowledge base
# ════════════════════════════════════════════════════════════
async def rag_lookup_node(state: SupportState) -> dict:
    """
    Semantic search over the tenant's knowledge base.
    Embeds the user query and finds top-5 similar documents.
    """
    query = state["user_input"]
    tenant_id = state["tenant_id"]

    try:
        # Embed the query
        query_embedding = embed_text(query)

        # Search pgvector
        from app.database import search_knowledge_base
        docs = await search_knowledge_base(
            tenant_id=tenant_id,
            embedding=query_embedding,
            limit=5,
        )

        if docs:
            # Format docs into a context string for the LLM
            context_parts = []
            for i, doc in enumerate(docs, 1):
                similarity = doc.get("similarity", 0)
                if similarity > 0.3:   # only include if reasonably similar
                    context_parts.append(
                        f"[Source {i}] {doc.get('title', 'Knowledge Base')}\n{doc['content']}"
                    )

            rag_context = "\n\n---\n\n".join(context_parts) if context_parts else ""
            logger.info(f"[rag_lookup] Found {len(docs)} docs, {len(context_parts)} above threshold")
        else:
            docs = []
            rag_context = ""
            logger.info("[rag_lookup] No knowledge base documents found")

    except Exception as e:
        logger.warning(f"[rag_lookup] DB search failed (DB not ready?): {e}")
        docs = []
        rag_context = ""

    return {
        "retrieved_docs": docs,
        "rag_context": rag_context,
    }


# ════════════════════════════════════════════════════════════
# NODE 5: TOOL CALL
# Handles intents that need data lookup (orders, billing, etc.)
# ════════════════════════════════════════════════════════════
async def tool_call_node(state: SupportState) -> dict:
    """
    Executes tool calls for data-dependent intents.
    In production these call real APIs/DB queries.
    For now they return realistic mock data.
    """
    intent = state["intent"]
    user_input = state["user_input"]
    tool_results = {}
    tool_name = None

    if intent == "order_status":
        tool_name = "order_lookup"
        # In production: query your orders database
        tool_results = {
            "tool": "order_lookup",
            "status": "In Transit",
            "order_id": "ORD-DEMO-001",
            "estimated_delivery": "2-3 business days",
            "carrier": "DHL",
            "tracking_number": "DHL123456789",
            "note": "This is demo data. Connect your orders DB for real data.",
        }

    elif intent == "refund_request":
        tool_name = "refund_processor"
        tool_results = {
            "tool": "refund_processor",
            "refund_eligible": True,
            "refund_amount": "Full amount",
            "processing_time": "3-5 business days",
            "refund_method": "Original payment method",
            "note": "This is demo data.",
        }

    elif intent == "billing":
        tool_name = "billing_lookup"
        tool_results = {
            "tool": "billing_lookup",
            "account_status": "Active",
            "next_billing_date": "2026-07-01",
            "amount_due": "$29.99",
            "payment_method": "Visa ending in 4242",
            "note": "This is demo data.",
        }

    if tool_name:
        logger.info(f"[tool_call] Called tool: {tool_name}")
        await kafka_producer.emit_tool_called(
            tenant_id=state["tenant_id"],
            conversation_id=state["conversation_id"],
            tool_name=tool_name,
        )

    return {
        "tool_results": tool_results,
        "tool_name": tool_name,
    }


# ════════════════════════════════════════════════════════════
# NODE 6: CO-PILOT
# Generates suggested replies for human agents
# ════════════════════════════════════════════════════════════
async def co_pilot_node(state: SupportState) -> dict:
    """
    Runs when a human agent is assigned to a ticket.
    Generates 3 suggested reply options for the agent to choose from.
    """
    if not state.get("copilot_active", False):
        return {"suggested_replies": []}

    llm = get_llm(temperature=0.7)  # Higher temp for variety in suggestions

    rag_context = state.get("rag_context", "")
    context_section = f"\nRelevant knowledge base:\n{rag_context}" if rag_context else ""

    prompt = f"""You are an AI assistant helping a human customer support agent.
Generate 3 different reply options for the agent to use.
Each reply should be professional, empathetic, and solve the customer's issue.
Make them meaningfully different in approach (direct/empathetic/detailed).

Customer message: "{state['user_input']}"
Intent: {state.get('intent', 'unknown')}{context_section}

Respond in JSON format only:
{{"suggestions": ["<reply 1>", "<reply 2>", "<reply 3>"]}}"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        result = json.loads(raw)
        suggestions = result.get("suggestions", [])[:3]
        logger.info(f"[co_pilot] Generated {len(suggestions)} suggestions")
    except Exception as e:
        logger.error(f"[co_pilot] Error: {e}")
        suggestions = [
            "Thank you for contacting us. I'm looking into your issue right now.",
            "I understand your concern. Let me check the details and get back to you shortly.",
            "I apologize for any inconvenience. I'll resolve this for you immediately.",
        ]

    return {"suggested_replies": suggestions}


# ════════════════════════════════════════════════════════════
# NODE 7: ESCALATE
# Hands off to a human agent
# ════════════════════════════════════════════════════════════
async def escalate_node(state: SupportState) -> dict:
    """
    Escalates the conversation to a human agent.
    Marks conversation as escalated in DB, sends notification.
    """
    reason = state.get("escalation_reason", "Customer requested human agent")
    logger.info(f"[escalate] Escalating conv {state['conversation_id'][:8]} | reason: {reason}")

    # Update DB
    try:
        from app.database import update_conversation_status
        await update_conversation_status(
            conversation_id=state["conversation_id"],
            status="escalated",
            escalation_reason=reason,
        )
    except Exception as e:
        logger.warning(f"[escalate] DB update failed: {e}")

    # Emit Kafka event
    await kafka_producer.emit_escalated(
        tenant_id=state["tenant_id"],
        conversation_id=state["conversation_id"],
        reason=reason,
    )

    # The response to the customer
    response = (
        "I understand this needs more attention. I'm connecting you with a human agent "
        "who will be with you shortly. Thank you for your patience."
    )

    if state.get("language") == "ur":
        response = (
            "میں سمجھتا ہوں کہ اس معاملے پر زیادہ توجہ کی ضرورت ہے۔ "
            "میں آپ کو ایک انسانی ایجنٹ سے جوڑ رہا ہوں جو جلد آپ کی مدد کریں گے۔"
        )

    return {
        "final_response": response,
        "should_escalate": True,
        "copilot_active": True,   # activate co-pilot for the human agent
        "is_resolved": False,
    }


# ════════════════════════════════════════════════════════════
# NODE 8: RESOLVE
# Generates final AI response and closes the conversation
# ════════════════════════════════════════════════════════════
async def resolve_node(state: SupportState) -> dict:
    """
    The main response generation node.
    Uses the system prompt, RAG context, tool results, and conversation
    history to generate the final response to the customer.
    """
    start_time = time.time()
    llm = get_llm(temperature=0.4)

    # Build context for the LLM
    system_prompt = state.get("system_prompt", DEFAULT_STATE_VALUES["system_prompt"])
    rag_context = state.get("rag_context", "")
    tool_results = state.get("tool_results", {})
    language = state.get("language", "en")

    # Build the system message
    system_content = system_prompt
    if rag_context:
        system_content += f"\n\nRelevant knowledge base information:\n{rag_context}"
    if tool_results:
        system_content += f"\n\nData retrieved from our systems:\n{json.dumps(tool_results, indent=2)}"
    if language == "ur":
        system_content += "\n\nIMPORTANT: Respond in Urdu language."

    messages_for_llm = [
        SystemMessage(content=system_content),
        HumanMessage(content=state["user_input"]),
    ]

    try:
        response = await llm.ainvoke(messages_for_llm)
        final_response = response.content.strip()
        model_used = "llama-3.3-70b-versatile"
    except Exception as e:
        logger.error(f"[resolve] LLM error: {e}")
        final_response = "I apologize, but I'm having trouble processing your request right now. Please try again in a moment."
        model_used = "fallback"

    latency_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[resolve] Generated response in {latency_ms}ms | model={model_used}")

    # Save response to DB
    try:
        from app.database import save_message, update_conversation_status
        await save_message(
            conversation_id=state["conversation_id"],
            role="assistant",
            content=final_response,
            model_used=model_used,
            latency_ms=latency_ms,
        )
        await update_conversation_status(
            conversation_id=state["conversation_id"],
            status="resolved",
            intent=state.get("intent"),
        )
    except Exception as e:
        logger.warning(f"[resolve] DB save failed: {e}")

    # Emit Kafka events
    await kafka_producer.emit_response_sent(
        tenant_id=state["tenant_id"],
        conversation_id=state["conversation_id"],
        latency_ms=latency_ms,
        model=model_used,
        tokens=len(final_response.split()),
    )

    return {
        "final_response": final_response,
        "model_used": model_used,
        "latency_ms": latency_ms,
        "is_resolved": True,
    }