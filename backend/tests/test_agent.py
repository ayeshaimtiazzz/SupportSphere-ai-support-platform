"""
backend/tests/test_agent.py
15 test cases for the LangGraph support agent.

Each test mocks the LLM and asserts correct node routing.
Run with: pytest tests/test_agent.py -v

Tests cover:
  - Node routing logic (which path the graph takes)
  - Intent classification
  - Escalation triggers
  - Language detection
  - Tool call routing
  - Edge cases
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agents.state import SupportState, DEFAULT_STATE_VALUES
from app.agents.graph import route_after_classify, route_after_escalate


# ─────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────

def make_state(**overrides) -> SupportState:
    """Create a test state with sensible defaults, override specific fields."""
    base = {
        **DEFAULT_STATE_VALUES,
        "tenant_id": "test-tenant-001",
        "customer_id": "test-customer-001",
        "conversation_id": "test-conv-001",
        "user_input": "Hello, I need help.",
        "channel": "web",
        "messages": [],
    }
    base.update(overrides)
    return base


# ─────────────────────────────────────────
# GROUP 1: Routing logic tests (no LLM needed)
# ─────────────────────────────────────────

class TestRouting:
    def test_route_to_escalate_when_should_escalate_true(self):
        """If should_escalate is True, router must choose 'escalate'."""
        state = make_state(should_escalate=True, escalation_reason="3 failed attempts")
        result = route_after_classify(state)
        assert result == "escalate"

    def test_route_to_tool_call_for_order_status(self):
        """order_status intent should route to tool_call."""
        state = make_state(intent="order_status", confidence=0.95, should_escalate=False)
        result = route_after_classify(state)
        assert result == "tool_call"

    def test_route_to_tool_call_for_refund_request(self):
        """refund_request intent should route to tool_call."""
        state = make_state(intent="refund_request", confidence=0.88, should_escalate=False)
        result = route_after_classify(state)
        assert result == "tool_call"

    def test_route_to_tool_call_for_billing(self):
        """billing intent should route to tool_call."""
        state = make_state(intent="billing", confidence=0.91, should_escalate=False)
        result = route_after_classify(state)
        assert result == "tool_call"

    def test_route_to_rag_for_general_faq(self):
        """general_faq does not need tool call — goes to rag_lookup."""
        state = make_state(intent="general_faq", confidence=0.87, should_escalate=False)
        result = route_after_classify(state)
        assert result == "rag_lookup"

    def test_route_to_rag_for_technical_issue(self):
        """technical_issue goes to rag_lookup (no data tool needed)."""
        state = make_state(intent="technical_issue", confidence=0.82, should_escalate=False)
        result = route_after_classify(state)
        assert result == "rag_lookup"

    def test_route_to_rag_for_unknown_with_low_attempts(self):
        """unknown intent with < 3 attempts should NOT escalate, goes to rag_lookup."""
        state = make_state(intent="unknown", confidence=0.2, should_escalate=False, attempt_count=1)
        result = route_after_classify(state)
        assert result == "rag_lookup"

    def test_escalate_takes_priority_over_intent(self):
        """should_escalate flag beats the intent — even order_status escalates if flag is set."""
        state = make_state(intent="order_status", should_escalate=True)
        result = route_after_classify(state)
        assert result == "escalate"

    def test_route_after_escalate_with_copilot_active(self):
        """After escalation, if copilot_active=True, go to co_pilot node."""
        state = make_state(should_escalate=True, copilot_active=True)
        result = route_after_escalate(state)
        assert result == "co_pilot"

    def test_route_after_escalate_without_copilot(self):
        """After escalation with no agent assigned, go straight to END."""
        state = make_state(should_escalate=True, copilot_active=False)
        result = route_after_escalate(state)
        assert result == "__end__"


# ─────────────────────────────────────────
# GROUP 2: Node unit tests (mock LLM)
# ─────────────────────────────────────────

class TestNodes:

    @pytest.mark.asyncio
    async def test_classify_intent_order_status(self):
        """classify_intent_node should return order_status for order queries."""
        from app.agents.nodes import classify_intent_node

        llm_response = MagicMock()
        llm_response.content = json.dumps({
            "intent": "order_status",
            "confidence": 0.95,
            "reasoning": "Customer asking about order delivery"
        })

        with patch("app.agents.nodes.get_llm") as mock_get_llm, \
             patch("app.agents.nodes.kafka_producer.emit_intent_classified", new_callable=AsyncMock):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = llm_response
            mock_get_llm.return_value = mock_llm

            state = make_state(user_input="Where is my order ORD-12345?")
            result = await classify_intent_node(state)

        assert result["intent"] == "order_status"
        assert result["confidence"] == 0.95
        assert result["should_escalate"] == False

    @pytest.mark.asyncio
    async def test_classify_intent_escalates_after_3_unknown(self):
        """After 3 failed attempts with unknown intent, should_escalate becomes True."""
        from app.agents.nodes import classify_intent_node

        llm_response = MagicMock()
        llm_response.content = json.dumps({
            "intent": "unknown",
            "confidence": 0.1,
            "reasoning": "Cannot determine intent"
        })

        with patch("app.agents.nodes.get_llm") as mock_get_llm, \
             patch("app.agents.nodes.kafka_producer.emit_intent_classified", new_callable=AsyncMock):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = llm_response
            mock_get_llm.return_value = mock_llm

            # Simulate 3rd attempt
            state = make_state(user_input="asdfghjkl", attempt_count=2)
            result = await classify_intent_node(state)

        assert result["intent"] == "unknown"
        assert result["should_escalate"] == True
        assert result["attempt_count"] == 3

    @pytest.mark.asyncio
    async def test_language_detect_urdu_heuristic(self):
        """Language detection should detect Urdu from Unicode characters without LLM."""
        from app.agents.nodes import language_detect_node

        # Urdu text: "میرا آرڈر کہاں ہے" (Where is my order)
        urdu_text = "میرا آرڈر کہاں ہے؟ مجھے مدد چاہیے"
        state = make_state(user_input=urdu_text)

        result = await language_detect_node(state)
        assert result["language"] == "ur"

    @pytest.mark.asyncio
    async def test_language_detect_english(self):
        """English text should be detected as 'en'."""
        from app.agents.nodes import language_detect_node

        with patch("app.agents.nodes.get_llm") as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = MagicMock(content="en")
            mock_get_llm.return_value = mock_llm

            state = make_state(user_input="Hello, I need help with my account.")
            result = await language_detect_node(state)

        assert result["language"] == "en"

    @pytest.mark.asyncio
    async def test_tool_call_order_status(self):
        """tool_call_node should return order data for order_status intent."""
        from app.agents.nodes import tool_call_node

        with patch("app.agents.nodes.kafka_producer.emit_tool_called", new_callable=AsyncMock):
            state = make_state(intent="order_status")
            result = await tool_call_node(state)

        assert result["tool_name"] == "order_lookup"
        assert "status" in result["tool_results"]
        assert result["tool_results"]["tool"] == "order_lookup"

    @pytest.mark.asyncio
    async def test_tool_call_refund_request(self):
        """tool_call_node should return refund info for refund_request intent."""
        from app.agents.nodes import tool_call_node

        with patch("app.agents.nodes.kafka_producer.emit_tool_called", new_callable=AsyncMock):
            state = make_state(intent="refund_request")
            result = await tool_call_node(state)

        assert result["tool_name"] == "refund_processor"
        assert result["tool_results"]["refund_eligible"] == True

    @pytest.mark.asyncio
    async def test_tool_call_no_tool_for_faq(self):
        """general_faq should NOT trigger any tool call."""
        from app.agents.nodes import tool_call_node

        state = make_state(intent="general_faq")
        result = await tool_call_node(state)

        assert result["tool_name"] is None
        assert result["tool_results"] == {}

    @pytest.mark.asyncio
    async def test_resolve_node_generates_response(self):
        """resolve_node should call LLM and return a final_response."""
        from app.agents.nodes import resolve_node

        mock_response = MagicMock()
        mock_response.content = "Your order ORD-12345 is currently in transit and will arrive in 2-3 business days."

        with patch("app.agents.nodes.get_llm") as mock_get_llm, \
             patch("app.agents.nodes.kafka_producer.emit_response_sent", new_callable=AsyncMock), \
             patch("app.agents.nodes.save_message", new_callable=AsyncMock, create=True), \
             patch("app.agents.nodes.update_conversation_status", new_callable=AsyncMock, create=True):
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            state = make_state(
                user_input="Where is my order?",
                intent="order_status",
                tool_results={"status": "In Transit", "order_id": "ORD-12345"},
            )
            result = await resolve_node(state)

        assert result["final_response"] is not None
        assert len(result["final_response"]) > 10
        assert result["is_resolved"] == True
        assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_escalate_node_sets_flags(self):
        """escalate_node should set is_resolved=False and copilot_active=True."""
        from app.agents.nodes import escalate_node

        with patch("app.agents.nodes.kafka_producer.emit_escalated", new_callable=AsyncMock), \
             patch("app.database.update_conversation_status", new_callable=AsyncMock, create=True):
            state = make_state(
                should_escalate=True,
                escalation_reason="Cannot understand request after 3 attempts"
            )
            result = await escalate_node(state)

        assert result["is_resolved"] == False
        assert result["copilot_active"] == True
        assert result["final_response"] is not None
        assert "agent" in result["final_response"].lower() or "human" in result["final_response"].lower()

    @pytest.mark.asyncio
    async def test_intake_node_adds_user_message(self):
        """intake_node should add the user input as a HumanMessage."""
        from app.agents.nodes import intake_node
        from langchain_core.messages import HumanMessage

        with patch("app.agents.nodes.kafka_producer.emit_message_received", new_callable=AsyncMock):
            state = make_state(user_input="I need a refund please")
            result = await intake_node(state)

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], HumanMessage)
        assert result["messages"][0].content == "I need a refund please"