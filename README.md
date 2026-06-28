# SupportSphere — Production-Grade AI Customer Support Platform

> Multi-tenant AI customer support system with voice input, WhatsApp integration, fine-tuned LLM, real-time analytics, and an agent co-pilot dashboard.

**Built by:** Ayesha Imtiaz · [github.com/ayeshaimtiazzz](https://github.com/ayeshaimtiazzz) · ayeshaimtiaz1663@gmail.com

---

## Live Demo

| Service | URL |
|---------|-----|
| Frontend | `http://localhost:3000` |
| API Docs | `http://localhost:8000/docs` |
| Grafana | `http://localhost:3001` |
| Prometheus | `http://localhost:9095` |

---

## What Is This?

SupportSphere is not a demo chatbot. It is a working, production-grade customer support platform that multiple companies could use simultaneously. It handles voice input, WhatsApp messages, and web chat — all routed through the same LangGraph agent — with a fine-tuned LLM, a real-time Kafka analytics pipeline, and a human agent co-pilot dashboard.

This is the kind of system that takes months to build at a company. It was built in stages over several weeks, hitting and solving real production problems along the way.

---

## Architecture

```
Customer (Web / WhatsApp / Voice)
        │
        ▼
FastAPI Backend (port 8000)
  ├── API key auth per tenant
  ├── Sliding window rate limiting (Redis)
  └── Routes: /conversations  /voice  /webhooks
        │
        ▼
LangGraph Agent (8-node state graph)
  intake → language_detect → classify_intent
        ├── [tool required]  → tool_call → rag_lookup → resolve
        ├── [faq/technical]  → rag_lookup → resolve
        └── [unknown ×3]     → escalate → co_pilot
        │
        ▼
Kafka (conversation_events topic)
        │
        ▼
Analytics Consumer → PostgreSQL daily_metrics
        │
        ▼
React Frontend (Analytics page / Recharts)
```

---

## Features

### Core: Multi-Tenant Architecture
Each company (tenant) has its own isolated knowledge base, conversation history, and custom LLM persona. Row Level Security (RLS) is implemented at the PostgreSQL level — even if application code has a bug, one tenant cannot see another's data. Rate limiting is enforced per tenant API key using Redis sorted sets.

### Voice Pipeline
The browser records audio using the `MediaRecorder` API and sends it to a FastAPI WebSocket endpoint. Groq's hosted Whisper (whisper-large-v3) transcribes the audio. The transcript is fed into the same LangGraph pipeline as text. Responses are optionally converted back to speech using gTTS.

### Fine-Tuned Support LLM
Mistral-7B-v0.3 was fine-tuned on 26,000 customer support examples from the Bitext dataset using QLoRA (4-bit NF4 quantization + LoRA rank=16) on a Google Colab T4 GPU. The merged model was uploaded to HuggingFace Hub. Training took approximately 2.5 hours.

### Real-Time Agent Co-Pilot
When a human agent opens a ticket, the right panel of the dashboard shows 3 AI-generated reply suggestions. The agent can click "Use this reply" to copy the suggestion into their response. Every suggestion and edit is logged for quality analysis.

### Kafka Event Streaming
Every conversation event (message received, intent classified, tool called, escalated, resolved) is published to a Kafka topic. A separate consumer service reads from the topic and writes aggregated metrics to a `daily_metrics` PostgreSQL table every 60 seconds.

### Bilingual Support
Automatic language detection for English and Urdu. Urdu Unicode characters are detected via a character range heuristic before falling back to an LLM call. Responses are generated in the detected language.

### Semantic Ticket Deduplication (RAG)
User queries are embedded using `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) and searched against the tenant's knowledge base using pgvector cosine similarity. The top-5 most similar chunks are retrieved and passed to the LLM as context.

---

## Tech Stack

| Tool | Category | Why it was used |
|------|----------|-----------------|
| **LangGraph** | Agent Orchestration | Models the support workflow as a typed state graph with 8 nodes and conditional routing. Enables durable, restartable multi-turn conversations via PostgresSaver checkpointing. |
| **FastAPI** | Web Framework | Async Python framework with built-in OpenAPI docs, WebSocket support, and dependency injection for API key auth. Prometheus instrumentation via `prometheus-fastapi-instrumentator`. |
| **Groq** | LLM Provider | Free-tier API for Llama 3.3-70B (intent classification + response generation) and Whisper-large-v3 (voice transcription). Sub-second latency for most requests. |
| **Mistral-7B** | Fine-tuned LLM | Base model fine-tuned on customer support data. Uploaded to HuggingFace Hub for serving. Used in A/B testing against Groq's Llama. |
| **PEFT / LoRA** | Fine-tuning | Parameter-efficient fine-tuning via Low-Rank Adaptation. Only 42M of 7.3B parameters are trained (~0.57%), making fine-tuning feasible on a free Colab T4. |
| **TRL / SFTTrainer** | Training Framework | Hugging Face's `SFTTrainer` handles tokenization, LoRA injection, gradient checkpointing, and evaluation in one training loop. |
| **sentence-transformers** | Embeddings | Local embedding model (`all-MiniLM-L6-v2`, 384 dims). Completely free, no API key required. Loads once at startup and stays in memory. |
| **PostgreSQL + pgvector** | Database + Vector Search | Single database for both relational data and vector similarity search. Eliminates the need for a separate vector database like Pinecone. |
| **Redis** | Caching + Rate Limiting | Sliding window rate limiter using Redis sorted sets (`ZREMRANGEBYSCORE`). Each tenant API key has a sorted set of request timestamps; old ones are removed on each check. |
| **Apache Kafka** | Event Streaming | Every agent action publishes to `conversation_events`. A separate consumer process reads the topic and aggregates metrics. Teaches producer/consumer offset management and at-least-once delivery. |
| **Twilio** | WhatsApp Integration | Webhook receives incoming WhatsApp messages as form-encoded POST requests. The same LangGraph agent processes them and replies via the Twilio REST API. |
| **Prometheus + Grafana** | Observability | Custom metrics: `messages_processed_total` (counter with tenant/intent labels), `response_latency_seconds` (histogram), `active_conversations_total` (gauge). Grafana dashboard with 4 panels. |
| **Docker Compose** | Infrastructure | Single `docker-compose.yml` orchestrates PostgreSQL (with pgvector), Redis, Kafka, Zookeeper, Prometheus, and Grafana. Named volumes persist data between restarts. |
| **React + TypeScript** | Frontend | Chat widget with voice input, agent dashboard with ticket queue and co-pilot panel, analytics page with Recharts, and a how-to documentation page. |
| **Recharts** | Data Visualization | Bar charts, line charts, pie charts, and horizontal bar charts for the analytics dashboard. |

---

## LangGraph Agent — 8 Nodes

```
Node 1: intake_node
  → Validates input, loads customer history from DB, publishes message_received to Kafka

Node 2: language_detect_node
  → Detects English vs Urdu via Unicode heuristic + LLM fallback

Node 3: classify_intent_node
  → Classifies into: order_status | refund_request | technical_issue | billing | general_faq | unknown
  → Returns confidence score. After 3 failed attempts → sets should_escalate=True

Node 4: rag_lookup_node
  → Embeds query with sentence-transformers
  → Searches pgvector for top-5 similar knowledge base chunks (cosine similarity > 0.3)

Node 5: tool_call_node
  → Handles order_status → order_lookup
  → Handles refund_request → refund_processor
  → Handles billing → billing_lookup

Node 6: co_pilot_node
  → Generates 3 suggested replies for human agents when copilot_active=True

Node 7: escalate_node
  → Sets is_resolved=False, copilot_active=True
  → Updates DB status to 'escalated', publishes to Kafka

Node 8: resolve_node
  → Builds system prompt + RAG context + tool results
  → Calls Groq LLM for final response
  → Saves to DB, publishes response_sent to Kafka
```

**Conditional routing:**
- `classify_intent` → `escalate` if `should_escalate=True`
- `classify_intent` → `tool_call` if intent in `{order_status, refund_request, billing}`
- `classify_intent` → `rag_lookup` for everything else
- `escalate` → `co_pilot` if human agent is assigned
- `tool_call` → `rag_lookup` → `resolve`

---

## Fine-Tuning Details

| Parameter | Value |
|-----------|-------|
| Base model | mistralai/Mistral-7B-v0.3 |
| Dataset | bitext/Bitext-customer-support-llm-chatbot-training-dataset |
| Training examples | 26,282 |
| Method | QLoRA (4-bit NF4 + LoRA) |
| LoRA rank | 16 |
| LoRA alpha | 32 |
| Target modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| Optimizer | paged_adamw_8bit |
| Learning rate | 2e-4 (cosine schedule) |
| Batch size | 2 × grad_accum 8 = effective 16 |
| Max steps | 500 |
| Hardware | NVIDIA T4 16GB (Google Colab free tier) |
| Precision | fp16 (T4 does not support bf16) |
| Training time | ~2.5 hours |
| HuggingFace | [ayeshaimtiazzz/supportsphere-mistral-support](https://huggingface.co) |

---

## Hard Problems Solved

### 1. PostgreSQL Port Conflict (Windows)
**Problem:** Docker's PostgreSQL on port 5432 conflicted with a locally installed PostgreSQL instance. The local instance intercepted all connections and rejected them with `password authentication failed for user "aimte"` (Windows username, not `support_user`).
**Solution:** Mapped Docker's PostgreSQL to port 5433 in `docker-compose.yml` and updated `DATABASE_URL` accordingly.

### 2. Mistral-7B bf16 Training Crash (Colab T4)
**Problem:** `NotImplementedError: "_amp_foreach_non_finite_check_and_unscale_cuda" not implemented for 'BFloat16'`. Setting `fp16=True` in SFTConfig activates PyTorch's GradScaler, but Mistral-7B-v0.3 has `torch_dtype: bfloat16` baked into its config, so some layers loaded in bf16. The GradScaler tried to unscale bf16 gradients, which is not implemented.
**Solution:** Set `fp16=False, bf16=False` (disabled mixed precision entirely). The 4-bit quantization already provides memory savings. Only the 42M LoRA adapter weights train in fp32, while the frozen base stays in 4-bit. Memory usage increased slightly (~10GB vs ~7GB) but training became stable.

### 3. torchao Version Conflict During LoRA Merge
**Problem:** `ImportError: Found an incompatible version of torchao. Found version 0.10.0, but only versions above 0.16.0 are supported` when calling `PeftModel.from_pretrained()` during the merge step.
**Solution:** `pip install -U torchao` before the merge cell. Did not require retraining — the saved adapter files on disk were unaffected.

### 4. Kafka Topic Initialization Failure (Windows)
**Problem:** The `kafka-init` container used a multiline bash heredoc (`entrypoint + command`) that does not parse correctly on Windows Docker. Topics were silently not created.
**Solution:** Changed to `command: >` with a single `bash -c "..."` string. Added a `sleep 10` wait before topic creation commands to allow Kafka to fully start.

### 5. sentence-transformers Blocking the Async Event Loop
**Problem:** The first request to the voice endpoint timed out (60+ seconds) because `sentence-transformers` was downloading and loading the `all-MiniLM-L6-v2` model (~90MB) synchronously inside an async FastAPI route, blocking the entire event loop.
**Solution:** Pre-load the embedding model at application startup inside the `lifespan` context manager, before `yield`. Subsequent requests use the cached in-memory model instantly.

### 6. LangGraph State Hanging After intake_node
**Problem:** Voice transcription succeeded and the agent started, but requests timed out after the `intake` node with no further logs.
**Solution:** Docker was not running, so PostgreSQL and Kafka were both unavailable. The agent was waiting on DB connections that never resolved. Starting Docker Compose immediately fixed the issue.

### 7. ElevenLabs 402 Payment Required
**Problem:** ElevenLabs free tier credits were exhausted mid-project.
**Solution:** Replaced ElevenLabs TTS with `gTTS` (Google Text-to-Speech), which is completely free with no API key or credit limit. The audio quality is slightly lower but sufficient for a portfolio demo.

### 8. .env Not Loading in Submodules
**Problem:** API keys set in `.env` were not visible inside service files (`voice.py`, `rate_limiter.py`) because `load_dotenv()` was only called in `main.py`, but the reloader spawns a new process where the env vars are not inherited.
**Solution:** Added `load_dotenv()` at the top of `main.py` before all other imports, and ensured the `.env` file is in the `backend/` directory (the working directory when uvicorn is run).

---

## Database Schema

```sql
tenants          -- companies using the platform (id, api_key, system_prompt, plan, rate_limit)
customers        -- end users (id, tenant_id, email, phone) — unique per tenant
conversations    -- support sessions (id, customer_id, tenant_id, status, channel, intent)
messages         -- individual messages (id, conversation_id, role, content, model_used, latency_ms)
knowledge_base   -- RAG documents (id, tenant_id, content, embedding vector(384))
daily_metrics    -- pre-aggregated analytics (tenant_id, date, totals, intent_breakdown)
```

Row Level Security is enabled on all tenant-scoped tables. The app sets `app.current_tenant_id` as a session variable before each query, and RLS policies use this to automatically filter rows.

---

## Local Setup

### Prerequisites
- Docker Desktop
- Python 3.10+
- Node.js 18+

### 1. Clone and configure
```bash
git clone https://github.com/ayeshaimtiazzz/SupportSphere
cd SupportSphere
cp backend/.env.example backend/.env
# Fill in: GROQ_API_KEY, TWILIO_*, HF_TOKEN, HF_MODEL_ID
```

### 2. Start infrastructure
```bash
docker-compose up -d postgres redis zookeeper kafka kafka-init prometheus grafana
# Wait 30 seconds for Kafka to initialize
```

### 3. Start backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 4. Start frontend
```bash
cd frontend
npm install
npm start
# Opens at http://localhost:3000
```

### 5. Start analytics consumer (optional)
```bash
cd backend
python -m app.services.analytics_consumer
```

### Test the API
```bash
curl -X POST http://localhost:8000/api/v1/conversations/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: acme_test_key_abc123" \
  -d '{"message": "Where is my order?"}'
```

---

## Project Structure

```
SupportSphere/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py                    # FastAPI app + lifespan
│       ├── database.py                # asyncpg connection pool + RLS helpers
│       ├── agents/
│       │   ├── state.py               # SupportState TypedDict
│       │   ├── nodes.py               # All 8 node functions
│       │   └── graph.py               # LangGraph assembly + routing
│       ├── api/
│       │   ├── health.py              # /health endpoint
│       │   ├── conversations.py       # /conversations REST endpoints
│       │   ├── voice.py               # /voice HTTP + WebSocket endpoints
│       │   └── webhooks.py            # /webhooks/whatsapp Twilio handler
│       └── services/
│           ├── embeddings.py          # sentence-transformers wrapper
│           ├── kafka_producer.py      # async Kafka event publisher
│           ├── rate_limiter.py        # Redis sliding window limiter
│           ├── voice.py               # Whisper STT + gTTS
│           ├── whatsapp.py            # Twilio REST API wrapper
│           └── analytics_consumer.py  # Kafka → PostgreSQL aggregator
├── frontend/
│   └── src/
│       ├── App.tsx                    # Router + sidebar
│       ├── components/
│       │   ├── chat/ChatWidget.tsx    # Floating chat widget + voice input
│       │   ├── dashboard/AgentDashboard.tsx  # Ticket queue + co-pilot
│       │   ├── analytics/AnalyticsPage.tsx   # Recharts analytics
│       │   └── docs/HowToPage.tsx     # Documentation page
│       ├── hooks/useChat.ts           # Chat state management
│       ├── services/api.ts            # Axios API client
│       └── types/index.ts             # TypeScript interfaces
├── infra/
│   ├── postgres/init.sql              # Schema + RLS + seed data
│   ├── prometheus/prometheus.yml
│   └── grafana/
│       ├── dashboards/
│       └── provisioning/
├── notebooks/
│   └── phase3_finetune_final.ipynb   # Mistral-7B QLoRA fine-tuning
└── scripts/
    ├── verify_kafka.py
    ├── verify_redis.py
    └── test_voice.py
```

---

## Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for instructions to deploy on Railway (backend) and Vercel (frontend).

---

## What I Learned

This project forced me to work with systems-level concerns that don't appear in tutorial projects: multi-tenant data isolation at the database level, Kafka consumer offset management, async event loop blocking from synchronous model loading, GPU memory constraints during LLM fine-tuning, and the difference between building something that works locally versus something that handles concurrent users correctly.

The LoRA fine-tuning was the most technically challenging part — not because of the training itself, but because of the three distinct failure modes encountered: the triton version conflict, the bf16/fp16 GradScaler mismatch on T4, and the torchao version incompatibility during merge. Each required understanding a different layer of the PyTorch/HuggingFace stack.

---

## Contact

Ayesha Imtiaz — BS Artificial Intelligence, NUCES-FAST Islamabad  
[github.com/ayeshaimtiazzz](https://github.com/ayeshaimtiazzz) · ayeshaimtiaz1663@gmail.com
