-- =============================================================================
-- Migration 001: Initial Schema for RazP Durable Persistence Layer
-- Applied via: python scripts/migrate.py
-- =============================================================================

BEGIN;

-- Migration tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------------------------
-- 1. Payment Cases — per-case lifecycle state
-- -------------------------------------------------------------------------
CREATE TABLE payment_cases (
    payment_id      TEXT PRIMARY KEY,
    invoice_id      TEXT NOT NULL,
    amount_inr      NUMERIC(15, 4) NOT NULL CHECK (amount_inr > 0),
    current_state   TEXT NOT NULL DEFAULT 'PAYMENT_FAILED',
    attempt_count   INTEGER NOT NULL DEFAULT 1 CHECK (attempt_count >= 0),
    contact_count   INTEGER NOT NULL DEFAULT 0 CHECK (contact_count >= 0),
    is_terminal     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_payment_cases_state    ON payment_cases(current_state);
CREATE INDEX idx_payment_cases_terminal ON payment_cases(is_terminal);

-- -------------------------------------------------------------------------
-- 2. State Transitions — full ordered history per case
-- -------------------------------------------------------------------------
CREATE TABLE state_transitions (
    id                SERIAL PRIMARY KEY,
    payment_id        TEXT NOT NULL REFERENCES payment_cases(payment_id) ON DELETE CASCADE,
    from_state        TEXT NOT NULL,
    to_state          TEXT NOT NULL,
    reason            TEXT NOT NULL DEFAULT '',
    transition_order  INTEGER NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_state_transitions_payment ON state_transitions(payment_id, transition_order);

-- -------------------------------------------------------------------------
-- 3. Processed Events — idempotency / replay protection
--    Stores canonical hashes, not raw payloads.
-- -------------------------------------------------------------------------
CREATE TABLE processed_events (
    event_hash          TEXT PRIMARY KEY,               -- SHA-256(event_id : payload_str)
    event_id            TEXT NOT NULL,
    payment_id          TEXT NOT NULL,
    payload_hash        TEXT NOT NULL,                   -- SHA-256(payload_str)
    first_processed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(event_id, payment_id)                        -- business-rule dedup
);

CREATE INDEX idx_processed_events_event_id ON processed_events(event_id);

-- -------------------------------------------------------------------------
-- 4. Audit Blocks — SHA-256 hash-chained immutable ledger
-- -------------------------------------------------------------------------
CREATE TABLE audit_blocks (
    block_index      INTEGER PRIMARY KEY,
    payment_id       TEXT NOT NULL,
    telemetry_hash   TEXT NOT NULL,
    ai_reasoning     JSONB,
    policy_decision  JSONB NOT NULL,
    action_executed  TEXT NOT NULL,
    resulting_state  TEXT NOT NULL,
    previous_hash    TEXT NOT NULL,
    current_hash     TEXT NOT NULL UNIQUE,
    block_timestamp  TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_blocks_payment ON audit_blocks(payment_id);

-- -------------------------------------------------------------------------
-- 5. Merchant Policies — runtime-configurable policy entity
-- -------------------------------------------------------------------------
CREATE TABLE merchant_policies (
    id                          SERIAL PRIMARY KEY,
    merchant_id                 TEXT NOT NULL,
    quiet_hours_start           TIME NOT NULL DEFAULT '21:00',
    quiet_hours_end             TIME NOT NULL DEFAULT '09:00',
    max_contact_attempts        INTEGER NOT NULL DEFAULT 3  CHECK (max_contact_attempts >= 1),
    max_ptp_extension_days      INTEGER NOT NULL DEFAULT 14 CHECK (max_ptp_extension_days >= 1),
    allow_discounts             BOOLEAN NOT NULL DEFAULT FALSE,
    circuit_breaker_threshold   NUMERIC(5, 4) NOT NULL DEFAULT 0.6500,
    cost_per_sms                NUMERIC(10, 4) NOT NULL DEFAULT 0.1500,
    cost_per_whatsapp           NUMERIC(10, 4) NOT NULL DEFAULT 0.5000,
    cost_per_llm_inference      NUMERIC(10, 4) NOT NULL DEFAULT 0.1000,
    cost_per_failed_bank_retry  NUMERIC(10, 4) NOT NULL DEFAULT 5.0000,
    chargeback_dispute_fee      NUMERIC(10, 4) NOT NULL DEFAULT 50.0000,
    is_active                   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Partial unique index: at most one active policy per merchant.
-- Equivalent to UNIQUE(merchant_id) WHERE is_active = TRUE.
CREATE UNIQUE INDEX idx_merchant_policies_active_unique
    ON merchant_policies(merchant_id) WHERE is_active = TRUE;

-- Seed the default policy (matches MerchantPolicy Pydantic defaults)
INSERT INTO merchant_policies (merchant_id, is_active)
VALUES ('rzp_merchant_prod', TRUE);

-- Record this migration
INSERT INTO schema_migrations (version) VALUES ('001_initial_schema');

COMMIT;
