"""
backend/app/services/kafka_producer.py
Publishes conversation events to Kafka topics.
Every significant action in the agent emits an event here.
These events are consumed by the analytics service.
"""

import json
import time
import logging
import os
from typing import Any, Optional
from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)

# Global producer instance
_producer: Optional[AIOKafkaProducer] = None


async def create_producer() -> AIOKafkaProducer:
    """Create and start the Kafka producer. Called once on app startup."""
    global _producer
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    _producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        # Reliability settings
        acks="all",             # wait for all replicas to acknowledge
        retry_backoff_ms=100,
        request_timeout_ms=10000,
    )
    await _producer.start()
    logger.info("Kafka producer started")
    return _producer


async def stop_producer():
    """Stop producer on app shutdown."""
    global _producer
    if _producer:
        await _producer.stop()
        logger.info("Kafka producer stopped")


async def publish_event(
    event_type: str,
    tenant_id: str,
    conversation_id: str,
    data: dict[str, Any],
    topic: str = "conversation_events",
) -> bool:
    """
    Publish a single event to Kafka.

    Args:
        event_type: e.g. 'message_received', 'intent_classified', 'escalated'
        tenant_id: which tenant this belongs to
        conversation_id: UUID of the conversation
        data: event-specific payload
        topic: Kafka topic name

    Returns:
        True if published successfully, False on error
    """
    global _producer
    if not _producer:
        logger.warning("Kafka producer not initialized — skipping event publish")
        return False

    event = {
        "event_type": event_type,
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "timestamp": time.time(),
        "data": data,
    }

    try:
        await _producer.send_and_wait(topic, event)
        logger.debug(f"Published event: {event_type} for conv {conversation_id[:8]}")
        return True
    except Exception as e:
        # Never let Kafka failures crash the main flow
        logger.error(f"Failed to publish Kafka event {event_type}: {e}")
        return False


# ─────────────────────────────────────────
# Convenience wrappers for each event type
# ─────────────────────────────────────────

async def emit_message_received(tenant_id: str, conversation_id: str, content: str, channel: str):
    await publish_event("message_received", tenant_id, conversation_id, {
        "content_length": len(content),
        "channel": channel,
    })


async def emit_intent_classified(tenant_id: str, conversation_id: str, intent: str, confidence: float):
    await publish_event("intent_classified", tenant_id, conversation_id, {
        "intent": intent,
        "confidence": confidence,
    })


async def emit_tool_called(tenant_id: str, conversation_id: str, tool_name: str):
    await publish_event("tool_called", tenant_id, conversation_id, {
        "tool": tool_name,
    })


async def emit_escalated(tenant_id: str, conversation_id: str, reason: str):
    await publish_event("escalated", tenant_id, conversation_id, {
        "reason": reason,
    })


async def emit_resolved(tenant_id: str, conversation_id: str, resolution_time_sec: float):
    await publish_event("conversation_resolved", tenant_id, conversation_id, {
        "resolution_time_sec": resolution_time_sec,
    })


async def emit_response_sent(
    tenant_id: str,
    conversation_id: str,
    latency_ms: int,
    model: str,
    tokens: int,
):
    await publish_event("response_sent", tenant_id, conversation_id, {
        "latency_ms": latency_ms,
        "model": model,
        "tokens": tokens,
    })