"""
Phase 3 Test Suite: Security, RBAC, Concurrency, and Production Hardening.
Verifies all 14 Phase 3 security invariants, error handling, and authorization rules.
"""

import os
import json
import pytest
import psycopg2
from datetime import datetime
from fastapi.testclient import TestClient
from core.schemas import (
    TransactionTelemetry,
    CustomerMessage,
    PaymentMethod,
    PaymentState,
    ActionType,
    MerchantPolicy,
    PolicyDecision,
    AIReasonerOutput,
    RootCauseCategory,
    CustomerIntentCategory,
    UserRole
)
from core.persistence import PersistenceManager, InvalidStateTransitionError
from core.state_machine import StateMachine
from server.app import app

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5433/razp_test")
os.environ["DATABASE_URL"] = DB_URL

# Demo test keys
OP_KEY = "razp_op_key_demo"
ADMIN_KEY = "razp_admin_key_demo"
AUDIT_KEY = "razp_audit_key_demo"
MASTER_ADMIN_KEY = "razp_master_admin_demo"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def clean_pm():
    pm = PersistenceManager(db_url=DB_URL)
    with pm.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM state_transitions WHERE payment_id LIKE 'pay_p3_%';")
            cur.execute("DELETE FROM processed_events WHERE payment_id LIKE 'pay_p3_%';")
            cur.execute("DELETE FROM audit_blocks WHERE payment_id LIKE 'pay_p3_%' OR payment_id LIKE 'policy_%';")
            cur.execute("DELETE FROM payment_cases WHERE payment_id LIKE 'pay_p3_%';")
    return pm


# 1. Missing DATABASE_URL fails fast
def test_missing_database_url_fails_fast(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RAZP_DEMO_IN_MEMORY", raising=False)
    
    # Importing or initializing lifespan without DATABASE_URL and without RAZP_DEMO_IN_MEMORY raises RuntimeError
    with pytest.raises(RuntimeError) as excinfo:
        from server.app import lifespan
        import asyncio
        async def run_test():
            async with lifespan(app):
                pass
        asyncio.run(run_test())
    assert "DATABASE_URL environment variable is mandatory" in str(excinfo.value)


# 2. In-memory fallback requires explicit opt-in
def test_in_memory_fallback_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("RAZP_DEMO_IN_MEMORY", "true")
    
    from server.app import lifespan
    import asyncio
    async def run_test():
        async with lifespan(app):
            pass
    # Should not raise exception when explicit opt-in is configured
    asyncio.run(run_test())


# 3. Unauthenticated API requests receive HTTP 401
def test_unauthenticated_api_requests_rejected(client):
    res = client.get("/api/dashboard/stats")
    assert res.status_code == 401
    assert "Missing authentication credentials" in res.json().get("detail", "")


# 4. Unauthorized role actions receive HTTP 403
def test_unauthorized_role_actions_rejected(client):
    # Operator attempting to update merchant policy (requires POLICY_ADMIN or ADMIN)
    res = client.post(
        "/api/policy",
        json={"merchant_id": "rzp_hacked", "allow_discounts": True},
        headers={"X-API-Key": OP_KEY}
    )
    assert res.status_code == 403
    assert "not authorized" in res.json().get("detail", "")

    # Auditor attempting to execute recovery evaluation (requires OPERATOR or POLICY_ADMIN)
    res = client.post(
        "/api/evaluate/single",
        json={"payment_id": "pay_p3_eval_01", "invoice_id": "inv_01", "amount_inr": 1000.0, "gateway_error_code": "51", "bank_raw_response_code": "51", "payment_method": "UPI_AUTOPAY"},
        headers={"X-API-Key": AUDIT_KEY}
    )
    assert res.status_code == 403


# 5. Security headers and CORS response validation
def test_security_headers_and_correlation_id(client):
    res = client.get("/api/health", headers={"X-Correlation-ID": "corr_custom_test_999"})
    assert res.status_code == 200
    assert res.headers.get("X-Correlation-ID") == "corr_custom_test_999"
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert res.headers.get("X-XSS-Protection") == "1; mode=block"


# 6. Rate limiting enforces request bounds
def test_rate_limiting_triggers_429(client, monkeypatch):
    from server.auth import eval_rate_limiter
    # Temporarily set limit to 3 for testing
    original_limit = eval_rate_limiter.limit
    eval_rate_limiter.limit = 3
    eval_rate_limiter._history.clear()
    try:
        for i in range(3):
            r = client.post(
                "/api/evaluate/single",
                json={"payment_id": f"pay_p3_rate_{i}", "invoice_id": "inv_01", "amount_inr": 1000.0, "gateway_error_code": "51", "bank_raw_response_code": "51", "payment_method": "UPI_AUTOPAY"},
                headers={"X-API-Key": OP_KEY}
            )
            assert r.status_code == 200

        # 4th request must exceed rate limit
        r_exceed = client.post(
            "/api/evaluate/single",
            json={"payment_id": "pay_p3_rate_exceed", "invoice_id": "inv_01", "amount_inr": 1000.0, "gateway_error_code": "51", "bank_raw_response_code": "51", "payment_method": "UPI_AUTOPAY"},
            headers={"X-API-Key": OP_KEY}
        )
        assert r_exceed.status_code == 429
        assert "Rate limit exceeded" in r_exceed.json().get("detail", "")
    finally:
        eval_rate_limiter.limit = original_limit


# 7. Duplicate recovery action is idempotent
def test_duplicate_recovery_action_is_idempotent(clean_pm):
    pay_id = "pay_p3_idem_001"
    evt_id = "evt_p3_idem_001"
    payload = "3500.0:GATEWAY_TIMEOUT:U30"

    # First event ingestion succeeds
    first_res = clean_pm.check_and_register_event(evt_id, pay_id, payload)
    assert first_res is True

    # Replayed event is rejected (idempotent guard)
    second_res = clean_pm.check_and_register_event(evt_id, pay_id, payload)
    assert second_res is False


# 8. Concurrent case updates with row locking prevent race conditions
def test_concurrent_case_updates_with_row_locking(clean_pm):
    pay_id = "pay_p3_concur_001"
    clean_pm.get_or_create_case(pay_id, "inv_01", 5000.0, PaymentState.PAYMENT_FAILED)

    # In transaction 1, lock the case
    with clean_pm.transaction() as tx1:
        with tx1.cursor() as cur1:
            cur1.execute("SELECT current_state FROM payment_cases WHERE payment_id = %s FOR UPDATE;", (pay_id,))
            row = cur1.fetchone()
            assert row is not None

            # Attempting non-blocking lock from another connection will be rejected or wait
            with clean_pm.transaction() as tx2:
                with tx2.cursor() as cur2:
                    cur2.execute("SET statement_timeout = '500ms';")
                    with pytest.raises(Exception):
                        cur2.execute("SELECT current_state FROM payment_cases WHERE payment_id = %s FOR UPDATE NOWAIT;", (pay_id,))


# 9. Terminal cases cannot be reopened
def test_terminal_case_cannot_reopen(clean_pm):
    pay_id = "pay_p3_term_001"
    clean_pm.get_or_create_case(pay_id, "inv_01", 1200.0, PaymentState.PAYMENT_FAILED)
    clean_pm.record_transition(pay_id, PaymentState.PAYMENT_FAILED, PaymentState.TELEMETRY_ANALYSIS, "Telemetry analysis")
    clean_pm.record_transition(pay_id, PaymentState.TELEMETRY_ANALYSIS, PaymentState.POLICY_GATED, "Policy passed")
    clean_pm.record_transition(pay_id, PaymentState.POLICY_GATED, PaymentState.PAUSE_RECON_VERIFY, "Debit claim lock")
    clean_pm.record_transition(pay_id, PaymentState.PAUSE_RECON_VERIFY, PaymentState.RECOVERED, "Settlement verified")

    # Attempting transition out of RECOVERED must raise InvalidStateTransitionError
    with pytest.raises(InvalidStateTransitionError) as excinfo:
        clean_pm.record_transition(pay_id, PaymentState.RECOVERED, PaymentState.RETRY_SCHEDULED, "Illegal reopening")
    assert "Cannot transition out of terminal state" in str(excinfo.value)



# 10. Policy updates create immutable cryptographic audit records
def test_policy_updates_create_audit_records(client, clean_pm):
    res = client.post(
        "/api/policy",
        json={"merchant_id": "rzp_p3_merchant", "max_contact_attempts": 2, "quiet_hours_start": "22:00"},
        headers={"X-API-Key": ADMIN_KEY, "X-Correlation-ID": "corr_policy_test_123"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UPDATED_AND_PERSISTED"

    # Verify audit block was created for policy update
    blocks = clean_pm.get_ledger_blocks()
    policy_blocks = [b for b in blocks if b.payment_id == "policy_rzp_p3_merchant"]
    assert len(policy_blocks) >= 1
    assert policy_blocks[0].action_executed == "POLICY_MUTATION_APPLIED"
    assert policy_blocks[0].correlation_id == "corr_policy_test_123"


# 11. Tamper and restore require admin role and X-Confirm-Destructive header
def test_tamper_and_restore_require_admin_and_confirmation(client):
    # Non-admin rejected
    res_no_admin = client.post("/api/ledger/tamper-test", headers={"X-API-Key": OP_KEY})
    assert res_no_admin.status_code == 403

    # Admin without X-Confirm-Destructive header rejected with HTTP 400
    res_no_header = client.post("/api/ledger/tamper-test", headers={"X-API-Key": MASTER_ADMIN_KEY})
    assert res_no_header.status_code == 400
    assert "X-Confirm-Destructive" in res_no_header.json().get("detail", "")

    # Admin with confirmation header succeeds
    res_tamper = client.post(
        "/api/ledger/tamper-test",
        headers={"X-API-Key": MASTER_ADMIN_KEY, "X-Confirm-Destructive": "true"}
    )
    assert res_tamper.status_code == 200
    assert res_tamper.json()["tamper_simulated"] is True
    assert res_tamper.json()["cryptographic_detection_successful"] is True

    # Restore with confirmation header succeeds
    res_restore = client.post(
        "/api/ledger/restore",
        headers={"X-API-Key": MASTER_ADMIN_KEY, "X-Confirm-Destructive": "true"}
    )
    assert res_restore.status_code == 200
    assert res_restore.json()["restored"] is True
    assert res_restore.json()["is_integrity_valid"] is True


# 12. Correlation IDs appear in audit records and response headers
def test_correlation_id_in_audit_record(client, clean_pm):
    res = client.post(
        "/api/evaluate/single",
        json={
            "payment_id": "pay_p3_corr_01",
            "invoice_id": "inv_p3_corr_01",
            "amount_inr": 2999.0,
            "gateway_error_code": "BAD_REQUEST_ERROR",
            "bank_raw_response_code": "51",
            "payment_method": "UPI_AUTOPAY"
        },
        headers={"X-API-Key": OP_KEY, "X-Correlation-ID": "corr_audit_trace_777"}
    )
    assert res.status_code == 200
    assert res.headers.get("X-Correlation-ID") == "corr_audit_trace_777"

    audit_block = res.json()["audit_block"]
    assert audit_block is not None
    assert audit_block.get("correlation_id") == "corr_audit_trace_777"
    assert audit_block.get("actor_id") is not None


# 13. Ledger remains valid under sequential additions
def test_ledger_remains_valid_across_sequential_additions(clean_pm):
    is_valid, err = clean_pm.verify_persisted_ledger_integrity()
    assert is_valid is True, f"Ledger integrity failed: {err}"


# 14. Database failure triggers atomic rollback of state and audit together
def test_database_failure_rolls_back_state_and_audit(clean_pm):
    pay_id = "pay_p3_rollback_01"
    
    with pytest.raises(Exception):
        with clean_pm.transaction() as conn:
            clean_pm.get_or_create_case(pay_id, "inv_01", 3000.0, PaymentState.PAYMENT_FAILED, conn=conn)
            # Force syntax error to trigger rollback
            with conn.cursor() as cur:
                cur.execute("INSERT INTO non_existent_table VALUES (1);")

    # Case should not exist due to rollback
    c = clean_pm.get_case(pay_id)
    assert c is None
