-- ai_logs_schema.sql — Database schema สำหรับ logging และ monitoring AI system
-- เป้าหมาย: PostgreSQL (ตรวจ syntax ด้วย pglast แล้ว ไม่ได้รันบนเซิร์ฟเวอร์จริง)
-- ใช้กับ SQLite ตรง ๆ ไม่ได้: มี BIGSERIAL, TIMESTAMPTZ, DEFAULT NOW() ต้องแก้ก่อน
-- ใช้กับ MySQL ตรง ๆ ไม่ได้: ไม่มี BIGSERIAL และ TIMESTAMPTZ

-- ── LLM Request Logs ─────────────────────────────────────────────────────────
CREATE TABLE llm_requests (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id      UUID,
    tag             VARCHAR(64),                          -- feature ที่เรียกใช้
    provider        VARCHAR(32) NOT NULL,                 -- anthropic | gemini | ollama
    model           VARCHAR(64) NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    latency_ms      INTEGER,
    prompt_hash     CHAR(64),                             -- SHA-256 ของ prompt (ไม่เก็บ raw)
    status          VARCHAR(16) DEFAULT 'success',        -- success | error | timeout
    error_message   TEXT
);

CREATE INDEX idx_llm_requests_created_at ON llm_requests (created_at DESC);
CREATE INDEX idx_llm_requests_tag        ON llm_requests (tag);
CREATE INDEX idx_llm_requests_provider   ON llm_requests (provider, model);

-- ── RAG Retrieval Logs ───────────────────────────────────────────────────────
CREATE TABLE rag_retrievals (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    query_hash      CHAR(64) NOT NULL,
    top_k           SMALLINT NOT NULL DEFAULT 4,
    avg_score       FLOAT,                                -- avg similarity score
    retrieved_ids   TEXT[],                               -- chunk IDs ที่ดึงมา
    latency_ms      INTEGER
);

-- ── Evaluation Results ───────────────────────────────────────────────────────
CREATE TABLE eval_results (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    request_id      BIGINT REFERENCES llm_requests(id),
    relevance       FLOAT CHECK (relevance BETWEEN 0 AND 1),
    faithfulness    FLOAT CHECK (faithfulness BETWEEN 0 AND 1),
    format_ok       BOOLEAN,
    eval_notes      TEXT
);

-- ── Knowledge Base (vector metadata) ────────────────────────────────────────
CREATE TABLE knowledge_chunks (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_file     TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL,
    char_start      INTEGER,
    char_end        INTEGER,
    token_estimate  INTEGER,
    content_hash    CHAR(64) UNIQUE,
    domain          VARCHAR(64),                          -- core-ai, engineering, etc.
    status          VARCHAR(16) DEFAULT 'active'          -- active | outdated
);

-- ── Useful views ─────────────────────────────────────────────────────────────

-- token usage per day + provider
CREATE VIEW daily_token_usage AS
SELECT
    DATE(created_at)       AS day,
    provider,
    model,
    COUNT(*)               AS requests,
    SUM(input_tokens)      AS total_input,
    SUM(output_tokens)     AS total_output,
    AVG(latency_ms)        AS avg_latency_ms,
    SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) AS errors
FROM llm_requests
GROUP BY DATE(created_at), provider, model
ORDER BY day DESC, total_output DESC;

-- average eval scores per tag
CREATE VIEW eval_by_feature AS
SELECT
    r.tag,
    COUNT(*)               AS evals,
    AVG(e.relevance)       AS avg_relevance,
    AVG(e.faithfulness)    AS avg_faithfulness,
    AVG(CASE WHEN e.format_ok THEN 1.0 ELSE 0.0 END) AS format_pass_rate
FROM eval_results e
JOIN llm_requests r ON r.id = e.request_id
WHERE r.tag IS NOT NULL
GROUP BY r.tag
ORDER BY avg_faithfulness DESC;

-- ── Sample queries ───────────────────────────────────────────────────────────

-- ค่าใช้จ่ายโดยประมาณ (Anthropic Haiku pricing)
-- SELECT day, ROUND(total_input * 0.00000025 + total_output * 0.00000125, 4) AS usd
-- FROM daily_token_usage WHERE provider = 'anthropic';

-- top degraded features (faithfulness < 0.7)
-- SELECT tag, avg_faithfulness FROM eval_by_feature WHERE avg_faithfulness < 0.7;
