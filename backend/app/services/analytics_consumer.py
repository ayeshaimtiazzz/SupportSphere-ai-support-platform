"""
backend/app/services/analytics_consumer.py
Kafka consumer that reads conversation_events and
aggregates them into the daily_metrics PostgreSQL table.

Run as a separate process:
    python -m app.services.analytics_consumer

It runs forever, consuming events and updating metrics every minute.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, date
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_consumer():
    from aiokafka import AIOKafkaConsumer
    import asyncpg

    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    db_url = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")

    consumer = AIOKafkaConsumer(
        "conversation_events",
        bootstrap_servers=bootstrap,
        group_id="analytics-consumer-group",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=False,   # manual commit for reliability
    )

    db = await asyncpg.create_pool(dsn=db_url, min_size=1, max_size=3)
    logger.info("Analytics consumer started")

    # In-memory accumulator — flushed to DB every minute
    # Structure: {(tenant_id, date): {metric: value}}
    buffer: dict = defaultdict(lambda: {
        "total_conversations": set(),   # set of conv IDs (deduplicate)
        "resolved_conversations": set(),
        "escalated_conversations": set(),
        "total_messages": 0,
        "resolution_times": [],
        "csat_scores": [],
        "intent_breakdown": defaultdict(int),
        "tool_usage": defaultdict(int),
    })

    await consumer.start()
    last_flush = asyncio.get_event_loop().time()

    try:
        async for msg in consumer:
            event = msg.value
            tenant_id = event.get("tenant_id", "unknown")
            conv_id = event.get("conversation_id", "")
            event_type = event.get("event_type", "")
            data = event.get("data", {})
            today = date.today().isoformat()
            key = (tenant_id, today)

            # Accumulate by event type
            if event_type == "message_received":
                buffer[key]["total_conversations"].add(conv_id)
                buffer[key]["total_messages"] += 1

            elif event_type == "intent_classified":
                intent = data.get("intent", "unknown")
                buffer[key]["intent_breakdown"][intent] += 1

            elif event_type == "conversation_resolved":
                buffer[key]["resolved_conversations"].add(conv_id)
                res_time = data.get("resolution_time_sec", 0)
                if res_time:
                    buffer[key]["resolution_times"].append(res_time)

            elif event_type == "escalated":
                buffer[key]["escalated_conversations"].add(conv_id)

            elif event_type == "tool_called":
                tool = data.get("tool", "unknown")
                buffer[key]["tool_usage"][tool] += 1

            # Flush to DB every 60 seconds
            now = asyncio.get_event_loop().time()
            if now - last_flush > 60:
                await flush_to_db(db, buffer)
                buffer.clear()
                last_flush = now
                await consumer.commit()

    finally:
        await consumer.stop()
        await db.close()


async def flush_to_db(db, buffer: dict):
    """Write accumulated metrics to daily_metrics table."""
    for (tenant_id, metric_date), data in buffer.items():
        total = len(data["total_conversations"])
        if total == 0:
            continue

        resolved = len(data["resolved_conversations"])
        escalated = len(data["escalated_conversations"])
        avg_res_time = (
            int(sum(data["resolution_times"]) / len(data["resolution_times"]))
            if data["resolution_times"] else 0
        )
        avg_csat = (
            round(sum(data["csat_scores"]) / len(data["csat_scores"]), 2)
            if data["csat_scores"] else None
        )

        try:
            async with db.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO daily_metrics
                        (tenant_id, date, total_conversations, resolved_conversations,
                         escalated_conversations, total_messages,
                         avg_resolution_time_sec, avg_csat_score,
                         intent_breakdown, tool_usage_breakdown)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (tenant_id, date) DO UPDATE SET
                        total_conversations     = daily_metrics.total_conversations + EXCLUDED.total_conversations,
                        resolved_conversations  = daily_metrics.resolved_conversations + EXCLUDED.resolved_conversations,
                        escalated_conversations = daily_metrics.escalated_conversations + EXCLUDED.escalated_conversations,
                        total_messages          = daily_metrics.total_messages + EXCLUDED.total_messages,
                        avg_resolution_time_sec = EXCLUDED.avg_resolution_time_sec,
                        avg_csat_score          = EXCLUDED.avg_csat_score,
                        intent_breakdown        = EXCLUDED.intent_breakdown,
                        tool_usage_breakdown    = EXCLUDED.tool_usage_breakdown,
                        updated_at              = NOW()
                    """,
                    tenant_id, metric_date, total, resolved, escalated,
                    data["total_messages"], avg_res_time, avg_csat,
                    json.dumps(dict(data["intent_breakdown"])),
                    json.dumps(dict(data["tool_usage"])),
                )
            logger.info(f"Flushed metrics for tenant {tenant_id[:8]} | date {metric_date} | {total} convs")
        except Exception as e:
            logger.error(f"DB flush error: {e}")


if __name__ == "__main__":
    asyncio.run(run_consumer())