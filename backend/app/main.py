"""
backend/app/main.py — Phase 4 version with voice + WhatsApp routes
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram, Gauge
import logging

from app.api.health import router as health_router
from app.api.conversations import router as conv_router
from app.api.voice import router as voice_router
from app.api.webhooks import router as webhook_router

from dotenv import load_dotenv
load_dotenv()  

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)

# ── Prometheus metrics ─────────────────────────────────────
messages_processed_total = Counter(
    "messages_processed_total", "Total messages processed",
    ["tenant_id", "intent", "channel"],
)
response_latency_seconds = Histogram(
    "response_latency_seconds", "AI response latency",
    ["tenant_id", "model_used"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)
active_conversations_total = Gauge(
    "active_conversations_total", "Open conversations right now",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")

    try:
        from app.database import create_pool
        await create_pool()
        logger.info("✅ PostgreSQL connected")
    except Exception as e:
        logger.warning(f"⚠️  PostgreSQL not available: {e}")

    try:
        from app.services.kafka_producer import create_producer
        await create_producer()
        logger.info("✅ Kafka producer started")
    except Exception as e:
        logger.warning(f"⚠️  Kafka not available: {e}")

    # ← ADD HERE (before yield)
    try:
        from app.services.embeddings import get_model
        get_model()
        logger.info("✅ Embedding model loaded")
    except Exception as e:
        logger.warning(f"⚠️  Embedding model not loaded: {e}")

    yield   # ← app runs here, everything above is startup

    # Everything below is shutdown
    try:
        from app.database import close_pool
        await close_pool()
    except Exception:
        pass
    try:
        from app.services.kafka_producer import stop_producer
        await stop_producer()
    except Exception:
        pass
    logger.info("Shutdown complete")


app = FastAPI(title="AI Customer Support Platform", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

app.include_router(health_router,  prefix="/api/v1",               tags=["health"])
app.include_router(conv_router,    prefix="/api/v1/conversations",  tags=["conversations"])
app.include_router(voice_router,   prefix="/api/v1/voice",          tags=["voice"])
app.include_router(webhook_router, prefix="/webhooks",              tags=["webhooks"])


@app.get("/")
async def root():
    return {"message": "AI Support Platform API", "docs": "/docs"}