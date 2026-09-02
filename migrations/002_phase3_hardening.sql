-- Migration 002: Phase 3 Security, Concurrency, and Audit Hardening
-- Adds audit metadata fields, indexed timestamptz column, and concurrency locks

ALTER TABLE audit_blocks
    ADD COLUMN IF NOT EXISTS block_timestamp_dt TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS correlation_id TEXT,
    ADD COLUMN IF NOT EXISTS actor_id TEXT,
    ADD COLUMN IF NOT EXISTS policy_version TEXT,
    ADD COLUMN IF NOT EXISTS model_name TEXT,
    ADD COLUMN IF NOT EXISTS prompt_version TEXT,
    ADD COLUMN IF NOT EXISTS before_state TEXT,
    ADD COLUMN IF NOT EXISTS after_state TEXT,
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT;

-- Backfill block_timestamp_dt from ISO text
UPDATE audit_blocks
SET block_timestamp_dt = block_timestamp::timestamptz
WHERE block_timestamp_dt IS NULL AND block_timestamp IS NOT NULL;

-- Create index on block_timestamp_dt for audit range queries
CREATE INDEX IF NOT EXISTS idx_audit_blocks_timestamp_dt ON audit_blocks(block_timestamp_dt DESC);
CREATE INDEX IF NOT EXISTS idx_audit_blocks_correlation_id ON audit_blocks(correlation_id);
CREATE INDEX IF NOT EXISTS idx_audit_blocks_actor_id ON audit_blocks(actor_id);
