-- -------------------------------------------------------------------------
-- RazP Migration 003: Idempotency Event Lifecycle (Pending, Processed, Failed)
-- -------------------------------------------------------------------------
ALTER TABLE processed_events ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'PROCESSED';
ALTER TABLE processed_events ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE processed_events ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
