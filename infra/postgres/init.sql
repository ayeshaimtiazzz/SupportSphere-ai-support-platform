-- ============================================================
-- PostgreSQL initialization script
-- Runs automatically on first container start
-- ============================================================

-- Enable pgvector extension (pre-installed in pgvector/pgvector image)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- for UUID primary keys

-- ============================================================
-- TENANTS
-- Each company using the platform is a "tenant"
-- ============================================================
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255) NOT NULL UNIQUE,
    api_key     VARCHAR(64)  NOT NULL UNIQUE,    -- hashed SHA-256 of the real key
    system_prompt TEXT,                           -- custom AI persona for this tenant
    plan        VARCHAR(50)  NOT NULL DEFAULT 'free',  -- free | starter | pro | enterprise
    rate_limit  INTEGER NOT NULL DEFAULT 100,    -- requests per minute
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- CUSTOMERS
-- End users who contact support
-- ============================================================
CREATE TABLE IF NOT EXISTS customers (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        VARCHAR(255),
    email       VARCHAR(255),
    phone       VARCHAR(50),
    language    VARCHAR(10) DEFAULT 'en',         -- 'en' or 'ur'
    metadata    JSONB DEFAULT '{}',               -- flexible extra fields
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, email)                      -- email unique per tenant, not globally
);

-- ============================================================
-- CONVERSATIONS
-- A single support session
-- ============================================================
CREATE TABLE IF NOT EXISTS conversations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id     UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    status          VARCHAR(50) NOT NULL DEFAULT 'open',  -- open | in_progress | escalated | resolved | closed
    channel         VARCHAR(50) NOT NULL DEFAULT 'web',   -- web | whatsapp | voice
    intent          VARCHAR(100),                          -- classified intent
    language        VARCHAR(10) DEFAULT 'en',
    assigned_agent  UUID,                                  -- human agent UUID if escalated
    escalation_reason TEXT,
    csat_score      SMALLINT CHECK (csat_score BETWEEN 1 AND 5),
    csat_requested  BOOLEAN DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- MESSAGES
-- Individual messages within a conversation
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL,    -- 'user' | 'assistant' | 'system' | 'tool'
    content         TEXT NOT NULL,
    tool_used       VARCHAR(100),            -- name of tool if role='tool'
    tool_input      JSONB,                   -- tool call arguments
    tool_output     JSONB,                   -- tool result
    tokens_input    INTEGER DEFAULT 0,
    tokens_output   INTEGER DEFAULT 0,
    model_used      VARCHAR(100),            -- 'gpt-4o' | 'mistral-finetuned' etc
    latency_ms      INTEGER,                 -- response time in milliseconds
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- KNOWLEDGE BASE
-- Tenant-specific documents for RAG retrieval
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_base (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title       VARCHAR(500),
    content     TEXT NOT NULL,
    embedding   vector(1536),               -- OpenAI text-embedding-3-small dimension
    metadata    JSONB DEFAULT '{}',         -- source, url, category, etc.
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- DAILY METRICS
-- Pre-aggregated analytics (written by Kafka consumer)
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_metrics (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    date                    DATE NOT NULL,
    total_conversations     INTEGER DEFAULT 0,
    resolved_conversations  INTEGER DEFAULT 0,
    escalated_conversations INTEGER DEFAULT 0,
    total_messages          INTEGER DEFAULT 0,
    avg_resolution_time_sec INTEGER DEFAULT 0,
    avg_csat_score          NUMERIC(3,2),
    intent_breakdown        JSONB DEFAULT '{}',  -- {"refund_request": 12, "billing": 5, ...}
    tool_usage_breakdown    JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, date)
);

-- ============================================================
-- INDEXES (performance)
-- ============================================================
-- Fast conversation lookup per tenant/customer
CREATE INDEX IF NOT EXISTS idx_conversations_tenant ON conversations(tenant_id);
CREATE INDEX IF NOT EXISTS idx_conversations_customer ON conversations(customer_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);
CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at DESC);

-- Fast message lookup per conversation
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);

-- Fast customer lookup per tenant
CREATE INDEX IF NOT EXISTS idx_customers_tenant ON customers(tenant_id);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(tenant_id, email);

-- pgvector cosine similarity index (IVFFlat — efficient for up to ~1M vectors)
-- Note: created after first data load for best performance
-- CREATE INDEX IF NOT EXISTS idx_kb_embedding
--     ON knowledge_base USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Daily metrics lookup
CREATE INDEX IF NOT EXISTS idx_daily_metrics_tenant_date ON daily_metrics(tenant_id, date DESC);

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- Prevents data leakage between tenants at DB level
-- Even if app code has a bug, one tenant cannot see another's data
-- ============================================================
ALTER TABLE customers       ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations   ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages        ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_base  ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_metrics   ENABLE ROW LEVEL SECURITY;

-- The app connects as 'support_user'. We set a session variable
-- current_tenant_id before each query. RLS policies use this.
CREATE POLICY tenant_isolation_customers ON customers
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);

CREATE POLICY tenant_isolation_conversations ON conversations
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);

CREATE POLICY tenant_isolation_knowledge_base ON knowledge_base
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);

CREATE POLICY tenant_isolation_daily_metrics ON daily_metrics
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);

-- Messages policy: accessible if the conversation belongs to current tenant
CREATE POLICY tenant_isolation_messages ON messages
    USING (
        conversation_id IN (
            SELECT id FROM conversations
            WHERE tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID
        )
    );

-- ============================================================
-- SEED DATA — two test tenants for development
-- ============================================================
INSERT INTO tenants (id, name, api_key, system_prompt, plan, rate_limit)
VALUES
(
    'a0000000-0000-0000-0000-000000000001',
    'Acme Corp',
    'acme_test_key_abc123',
    'You are Aria, a friendly customer support agent for Acme Corp. Be concise and helpful.',
    'pro',
    200
),
(
    'b0000000-0000-0000-0000-000000000002',
    'TechStart Ltd',
    'techstart_test_key_xyz789',
    'You are Max, a technical support specialist for TechStart. Focus on solving technical issues.',
    'starter',
    100
)
ON CONFLICT DO NOTHING;