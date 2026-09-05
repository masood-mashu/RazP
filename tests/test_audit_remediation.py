"""
Comprehensive Test Suite for Audit Remediation.
Validates:
1. Failed processing & retry behavior after reservation
2. Bank reconciliation HMAC signature, timestamp freshness, RRN & amount matching
3. Fail-closed production authentication & demo key rejection
4. Input bounds on SingleEvalRequest and WebhookReplayRequest
5. State transition from_state mismatch rejection
6. Zero-cost retention in policy updates (preventing 0.0 or default bug)
7. Non-negative cost validation on MerchantPolicy
8. In-memory engine isolation across concurrent payments
"""

import os
import time
import hmac
import hashlib
import json
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from fastapi.testclient import TestClient

from core.schemas import (
    MerchantPolicy,
    PaymentState,
    PaymentMethod,
    ActionType,
    BankSettlementWebhookPayload
)
from core.state_machine import StateMachine, InvalidStateTransitionError
from core.persistence import EventReservationStatus
from server.auth import (
    get_configured_keys,
    KNOWN_WEAK_KEYS,
    RateLimiter
)
from server.in_memory import InMemoryEngine
from server.app import app, SingleEvalRequest, WebhookReplayRequest, UpdatePolicyRequest

client = TestClient(app)
AUTH_HEADER = {"X-API-Key": "razp_master_admin_demo"}


# =============================================================================
# 1. Failed Processing & Retry Behavior (Requirement 3 & 7)
# =============================================================================

def test_failed_processing_allows_retry_after_release():
    """
    Verifies that if an event reservation is created, but subsequent processing
    fails, the reservation is marked FAILED / released so that a retry is granted.
    """
    engine = InMemoryEngine()
    event_id = "evt_fail_retry_001"
    payment_id = "pay_fail_retry_001"
    payload = "payload_content_123"

    # 1. First attempt: reserve
    res1 = engine.reserve_event(event_id, payment_id, payload)
    assert res1 == EventReservationStatus.NEW_RESERVED

    # 2. While PENDING, an immediate concurrent attempt is seen as IN_FLIGHT
    res_inflight = engine.reserve_event(event_id, payment_id, payload)
    assert res_inflight == EventReservationStatus.IN_FLIGHT

    # 3. Simulate failure during LLM execution / DB write
    engine.release_event_reservation(event_id, payment_id, "Simulation: LLM timeout")
    assert engine._events[(event_id, payment_id)]["status"] == "FAILED"

    # 4. Subsequent retry attempt: must be granted RETRY_RESERVED
    res2 = engine.reserve_event(event_id, payment_id, payload)
    assert res2 == EventReservationStatus.RETRY_RESERVED

    # 5. Success completion
    engine.complete_event(event_id, payment_id)
    assert engine._events[(event_id, payment_id)]["status"] == "PROCESSED"

    # 6. Future replay: must be ALREADY_PROCESSED
    res3 = engine.reserve_event(event_id, payment_id, payload)
    assert res3 == EventReservationStatus.ALREADY_PROCESSED


# =============================================================================
# 2. Bank Reconciliation Security (Requirement 2)
# =============================================================================

def test_bank_webhook_valid_hmac_reconciles_settlement():
    """
    Verifies valid HMAC-SHA256 signature with fresh timestamp, matching payment & amount
    transitions state to RECOVERED and sets recovered_amount authoritative value.
    """
    secret = "demo_bank_webhook_secret_for_local_testing"
    os.environ["BANK_WEBHOOK_SECRET"] = secret

    # Seed a case
    eval_resp = client.post(
        "/api/evaluate/single",
        json={
            "payment_id": "pay_recon_valid_001",
            "invoice_id": "inv_recon_001",
            "amount_inr": 4500.0,
            "gateway_error_code": "GATEWAY_TIMEOUT",
            "bank_raw_response_code": "U30",
            "payment_method": "UPI_AUTOPAY"
        },
        headers=AUTH_HEADER
    )
    assert eval_resp.status_code == 200

    now_ts = str(time.time())
    payload_dict = {
        "event_id": "evt_bank_settle_001",
        "payment_id": "pay_recon_valid_001",
        "settled_amount": 4500.0,
        "currency": "INR",
        "rrn": "RRN9988112233",
        "bank_status": "SETTLED"
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    payload_to_sign = f"{now_ts}.".encode("utf-8") + raw_body
    sig = hmac.new(secret.encode("utf-8"), payload_to_sign, hashlib.sha256).hexdigest()

    resp = client.post(
        "/api/webhook/bank-settlement",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Bank-Signature": sig,
            "X-Bank-Timestamp": now_ts
        }
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "SETTLEMENT_RECONCILED"
    assert data["recovered_amount"] == 4500.0
    assert data["resulting_state"] == "RECOVERED"
    assert data["rrn"] == "RRN9988112233"


def test_bank_webhook_rejects_stale_timestamp():
    """Verifies that bank webhooks with timestamp older than 300s are rejected."""
    secret = "demo_bank_webhook_secret_for_local_testing"
    stale_ts = str(time.time() - 400.0)  # 400 seconds in past
    payload_dict = {
        "event_id": "evt_stale_001",
        "payment_id": "pay_dummy",
        "settled_amount": 100.0,
        "currency": "INR",
        "rrn": "RRN123456",
        "bank_status": "SETTLED"
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    payload_to_sign = f"{stale_ts}.".encode("utf-8") + raw_body
    sig = hmac.new(secret.encode("utf-8"), payload_to_sign, hashlib.sha256).hexdigest()

    resp = client.post(
        "/api/webhook/bank-settlement",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Bank-Signature": sig,
            "X-Bank-Timestamp": stale_ts
        }
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


def test_bank_webhook_rejects_api_key_impersonation():
    """Verifies that standard API-key callers cannot call the bank webhook directly."""
    resp = client.post(
        "/api/webhook/bank-settlement",
        json={"dummy": "data"},
        headers={"X-API-Key": "razp_master_admin_demo"}
    )
    assert resp.status_code == 403


def test_bank_webhook_rejects_amount_mismatch():
    """Verifies that settlement amount mismatching the case amount is rejected."""
    secret = "demo_bank_webhook_secret_for_local_testing"

    # Seed case with amount 2500
    client.post(
        "/api/evaluate/single",
        json={
            "payment_id": "pay_mismatch_001",
            "invoice_id": "inv_mismatch_001",
            "amount_inr": 2500.0,
            "gateway_error_code": "GATEWAY_TIMEOUT",
            "bank_raw_response_code": "U30",
            "payment_method": "UPI_AUTOPAY"
        },
        headers=AUTH_HEADER
    )

    now_ts = str(time.time())
    payload_dict = {
        "event_id": "evt_mismatch_001",
        "payment_id": "pay_mismatch_001",
        "settled_amount": 1500.0,  # Mismatch: 1500 vs 2500
        "currency": "INR",
        "rrn": "RRN999999",
        "bank_status": "SETTLED"
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    payload_to_sign = f"{now_ts}.".encode("utf-8") + raw_body
    sig = hmac.new(secret.encode("utf-8"), payload_to_sign, hashlib.sha256).hexdigest()

    resp = client.post(
        "/api/webhook/bank-settlement",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Bank-Signature": sig,
            "X-Bank-Timestamp": now_ts
        }
    )
    assert resp.status_code == 422
    assert "amount mismatch" in resp.json()["detail"].lower()


# =============================================================================
# 3. Fail-Closed Authentication & Rejection of Demo Keys (Requirement 5)
# =============================================================================

def test_production_auth_fails_closed_when_keys_missing(monkeypatch):
    """Verifies that in production mode, missing RAZP_API_KEYS raises RuntimeError."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("RAZP_API_KEYS", raising=False)

    with pytest.raises(RuntimeError) as exc:
        get_configured_keys()
    assert "failing closed" in str(exc.value).lower() or "startup aborted" in str(exc.value).lower()


def test_production_auth_rejects_known_demo_keys(monkeypatch):
    """Verifies that configuring known demo keys in production mode is strictly rejected."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    bad_keys = json.dumps({"razp_master_admin_demo": "ADMIN"})
    monkeypatch.setenv("RAZP_API_KEYS", bad_keys)

    with pytest.raises(RuntimeError) as exc:
        get_configured_keys()
    assert "known demo key" in str(exc.value).lower() or "refusing startup" in str(exc.value).lower()


# =============================================================================
# 4. Input Bounds on Schemas (Requirement 6)
# =============================================================================

def test_single_eval_request_bounds():
    """Verifies input bounds on SingleEvalRequest."""
    # Negative amount rejected
    with pytest.raises(ValidationError):
        SingleEvalRequest(amount_inr=-50.0)

    # Zero amount rejected
    with pytest.raises(ValidationError):
        SingleEvalRequest(amount_inr=0.0)

    # Exorbitant amount rejected
    with pytest.raises(ValidationError):
        SingleEvalRequest(amount_inr=15_000_000.0)

    # Negative latency rejected
    with pytest.raises(ValidationError):
        SingleEvalRequest(latency_ms=-10)

    # Negative attempt count rejected
    with pytest.raises(ValidationError):
        SingleEvalRequest(attempt_count=0)

    # Invalid payment method rejected (not silently converted)
    with pytest.raises(ValidationError):
        SingleEvalRequest(payment_method="BITCOIN_LIGHTNING")


def test_merchant_policy_cost_bounds():
    """Verifies ge=0.0 on MerchantPolicy cost fields."""
    with pytest.raises(ValidationError):
        MerchantPolicy(cost_per_sms=-0.05)

    with pytest.raises(ValidationError):
        MerchantPolicy(cost_per_failed_bank_retry=-1.0)


# =============================================================================
# 5. State Transition from_state Mismatch (Requirement 7 & Audit Finding)
# =============================================================================

def test_record_transition_rejects_mismatched_from_state():
    """Verifies that record_transition rejects caller's forged/mismatched from_state."""
    engine = InMemoryEngine()
    payment_id = "pay_test_from_state"
    engine.get_or_create_case(payment_id, initial_state=PaymentState.PAYMENT_FAILED)

    # Actual current state is PAYMENT_FAILED. Caller claims from_state is AWAITING_CUSTOMER_ACTION
    with pytest.raises(InvalidStateTransitionError) as exc:
        engine.record_transition(
            payment_id=payment_id,
            from_state=PaymentState.AWAITING_CUSTOMER_ACTION,
            to_state=PaymentState.RECOVERED,
            reason="Forged transition test"
        )
    assert "State conflict" in str(exc.value)


# =============================================================================
# 6. Policy Zero-Cost Retention (Preventing 0.0 or default bug)
# =============================================================================

def test_policy_update_retains_zero_values():
    """Verifies that updating policy with 0.0 is retained and not replaced with defaults."""
    resp = client.post(
        "/api/policy",
        json={
            "merchant_id": "rzp_zero_test",
            "cost_per_sms": 0.0,
            "cost_per_whatsapp": 0.0,
            "cost_per_failed_bank_retry": 0.0
        },
        headers=AUTH_HEADER
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["policy"]
    assert data["cost_per_sms"] == 0.0
    assert data["cost_per_whatsapp"] == 0.0
    assert data["cost_per_failed_bank_retry"] == 0.0


# =============================================================================
# 7. In-Memory Engine Multi-Payment Isolation (Requirement 4)
# =============================================================================

def test_in_memory_multi_payment_isolation():
    """Verifies that separate payments do not share or corrupt each other's state machines."""
    engine = InMemoryEngine()
    sm1, c1 = engine.get_or_create_case("pay_iso_A", initial_state=PaymentState.PAYMENT_FAILED)
    sm2, c2 = engine.get_or_create_case("pay_iso_B", initial_state=PaymentState.PAYMENT_FAILED)

    # Transition pay_iso_A to TELEMETRY_ANALYSIS
    engine.record_transition("pay_iso_A", PaymentState.PAYMENT_FAILED, PaymentState.TELEMETRY_ANALYSIS, "Step A")

    # pay_iso_A should have moved, but pay_iso_B must still be PAYMENT_FAILED
    assert sm1.current_state == PaymentState.TELEMETRY_ANALYSIS
    assert engine.get_case("pay_iso_A")["current_state"] == "TELEMETRY_ANALYSIS"

    assert sm2.current_state == PaymentState.PAYMENT_FAILED
    assert engine.get_case("pay_iso_B")["current_state"] == "PAYMENT_FAILED"


# =============================================================================
# 8. Bounded Rate Limiter Memory Eviction
# =============================================================================

def test_rate_limiter_bounded_eviction():
    """Verifies that RateLimiter bounds its dictionary size and prunes stale buckets."""
    limiter = RateLimiter(requests_per_minute=100, max_tracked_buckets=50)

    # Fill beyond max buckets with dummy timestamps
    for i in range(100):
        limiter._history[f"key_{i}"] = [time.time() - 100.0]  # Expired timestamps

    class DummyReq:
        client = None
        headers = {"X-API-Key": "test_burst_token"}

    # Trigger rate limit check
    limiter.check_rate_limit(DummyReq(), "test")

    # Pruning must bring tracked buckets below or equal to max threshold
    assert len(limiter._history) <= 50
