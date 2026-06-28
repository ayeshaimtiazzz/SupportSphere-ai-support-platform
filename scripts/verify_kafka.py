"""
scripts/verify_kafka.py
Run this AFTER docker-compose up to verify Kafka topics work correctly.

Usage:
    python scripts/verify_kafka.py
"""

import asyncio
import json
import time
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC = "conversation_events"


async def produce_test_events():
    """Send 5 test events to Kafka."""
    producer = AIOKafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()

    events = [
        {
            "event_type": "message_received",
            "tenant_id": "a0000000-0000-0000-0000-000000000001",
            "conversation_id": "test-conv-001",
            "timestamp": time.time(),
            "data": {"content": "I need help with my order", "channel": "web"},
        },
        {
            "event_type": "intent_classified",
            "tenant_id": "a0000000-0000-0000-0000-000000000001",
            "conversation_id": "test-conv-001",
            "timestamp": time.time(),
            "data": {"intent": "order_status", "confidence": 0.92},
        },
        {
            "event_type": "tool_called",
            "tenant_id": "a0000000-0000-0000-0000-000000000001",
            "conversation_id": "test-conv-001",
            "timestamp": time.time(),
            "data": {"tool": "order_lookup", "order_id": "ORD-12345"},
        },
        {
            "event_type": "message_sent",
            "tenant_id": "a0000000-0000-0000-0000-000000000001",
            "conversation_id": "test-conv-001",
            "timestamp": time.time(),
            "data": {"latency_ms": 850, "model": "gpt-4o", "tokens": 143},
        },
        {
            "event_type": "conversation_resolved",
            "tenant_id": "a0000000-0000-0000-0000-000000000001",
            "conversation_id": "test-conv-001",
            "timestamp": time.time(),
            "data": {"resolution_time_sec": 45},
        },
    ]

    for event in events:
        await producer.send_and_wait(TOPIC, event)
        print(f"✅ Produced: {event['event_type']}")

    await producer.stop()
    print(f"\nSent {len(events)} events to topic '{TOPIC}'")


async def consume_test_events():
    """Read events back from Kafka to verify they were stored."""
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id="verify-consumer-group",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",   # read from beginning
        enable_auto_commit=True,
    )
    await consumer.start()

    print(f"\nConsuming from '{TOPIC}'...")
    count = 0
    try:
        async for msg in consumer:
            event = msg.value
            print(f"📨 Received [{msg.offset}]: {event['event_type']} "
                  f"| tenant: {event['tenant_id'][:8]}... "
                  f"| conv: {event['conversation_id']}")
            count += 1
            if count >= 5:  # stop after 5 messages for verification
                break
    finally:
        await consumer.stop()

    print(f"\n✅ Successfully consumed {count} events. Kafka is working correctly!")


async def main():
    print("=" * 50)
    print("Kafka Verification Script")
    print("=" * 50)
    print("\n[1] Producing test events...")
    await produce_test_events()

    await asyncio.sleep(1)  # let Kafka settle

    print("\n[2] Consuming events back...")
    await consume_test_events()


if __name__ == "__main__":
    asyncio.run(main())