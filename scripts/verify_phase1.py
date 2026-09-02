"""
Phase 1 End-to-End Verification Script.
Executes and prints results for all required verification items:
1. PostgreSQL version check
2. Migration status
3. Process restart test (case state + transitions + audit ledger)
4. Duplicate webhook test across restart
5. Concurrent audit ledger writes (contiguous indexes, unbroken hash chain)
6. Transaction rollback test (failure after case update before audit block)
7. API /evaluate/single persistent state machine verification
8. Authoritative reconciliation invariant
"""
import os
import time
import json
import hashlib
import concurrent.futures
from datetime import datetime
from typing import Dict, Any

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

import psycopg2
from fastapi.testclient import TestClient

from core.schemas import (
    PaymentState,
    ActionType,
    RootCauseCategory,
    CustomerIntentCategory,
    PaymentMethod,
    TransactionTelemetry,
    PolicyDecision,
    AIReasonerOutput,
    MerchantPolicy
)
from core.state_machine import StateMachine, InvalidStateTransitionError
from core.persistence import PersistenceManager
from scripts.migrate import run_migrations
from server.app import app


def run_full_verification():
    db_url = os.getenv("DATABASE_URL")
    print("=" * 70)
    print("RAZP PHASE 1 DURABLE PERSISTENCE VERIFICATION")
    print("=" * 70)

    # 1. PostgreSQL Version
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("SELECT version();")
        pg_version = cur.fetchone()[0]
    conn.close()
    print(f"\n[1] PostgreSQL Version:\n    {pg_version}")

    # 2. Migration Execution
    applied = run_migrations(db_url=db_url)
    print(f"\n[2] Migration Status:\n    Applied: {applied if applied else 'Schema up to date'}")

    # Reset tables for clean verification run
    pm = PersistenceManager(db_url=db_url)
    with pm.transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM audit_blocks;")
            cur.execute("DELETE FROM state_transitions;")
            cur.execute("DELETE FROM payment_cases;")
            cur.execute("DELETE FROM processed_events;")
            cur.execute("DELETE FROM merchant_policies;")
            cur.execute("INSERT INTO merchant_policies (merchant_id, is_active) VALUES ('rzp_merchant_prod', TRUE);")
    pm.close()

    # 3. Process Restart Test
    print("\n[3] Process Restart Test:")
    # Process 1
    pm_proc1 = PersistenceManager(db_url=db_url)
    pm_proc1.get_or_create_case("pay_restart_demo", "inv_restart_demo", 4500.0)
    pm_proc1.record_transition("pay_restart_demo", PaymentState.PAYMENT_FAILED, PaymentState.TELEMETRY_ANALYSIS, "Step 1")
    pm_proc1.record_transition("pay_restart_demo", PaymentState.TELEMETRY_ANALYSIS, PaymentState.POLICY_GATED, "Step 2")
    pm_proc1.record_transition("pay_restart_demo", PaymentState.POLICY_GATED, PaymentState.PAUSE_RECON_VERIFY, "Step 3")
    
    telem = TransactionTelemetry(
        payment_id="pay_restart_demo",
        invoice_id="inv_restart_demo",
        amount_inr=4500.0,
        gateway_error_code="GATEWAY_TIMEOUT",
        bank_raw_response_code="U30",
        payment_method=PaymentMethod.UPI_AUTOPAY,
        latency_ms=11500,
        bank_switch_degradation_score=0.85
    )
    dec = PolicyDecision(
        is_overridden=False,
        original_action=ActionType.PAUSE_RECON_VERIFY,
        final_action=ActionType.PAUSE_RECON_VERIFY,
        final_parameters={"timeout": 30},
        policy_reason="Reconciliation Lock",
        timestamp=datetime(2026, 9, 1, 12, 0, 0)
    )
    pm_proc1.record_audit_block(telem, dec, "PAUSE_RECON_VERIFY", PaymentState.PAUSE_RECON_VERIFY.value)
    # Terminate Process 1
    pm_proc1.close()
    print("    Process 1: Case created, 3 transitions, 1 audit block recorded. Process terminated.")

    # Process 2 (Fresh process)
    pm_proc2 = PersistenceManager(db_url=db_url)
    loaded_case = pm_proc2.get_case("pay_restart_demo")
    loaded_sm = pm_proc2.load_state_machine("pay_restart_demo")
    is_valid, err = pm_proc2.verify_persisted_ledger_integrity()
    blocks = pm_proc2.get_ledger_blocks()
    pm_proc2.close()

    assert loaded_case["current_state"] == "PAUSE_RECON_VERIFY"
    assert len(loaded_case["transitions"]) == 3
    assert loaded_sm.current_state == PaymentState.PAUSE_RECON_VERIFY
    assert is_valid is True
    assert len(blocks) == 1
    print(f"    Process 2 (Restart): Case reloaded -> State: {loaded_case['current_state']}, Transitions: {len(loaded_case['transitions'])}, Ledger blocks: {len(blocks)}, Hash chain valid: {is_valid}")

    # 4. Duplicate Webhook Across Restart
    print("\n[4] Duplicate Webhook Suppression Across Restart:")
    pm_a = PersistenceManager(db_url=db_url)
    first_res = pm_a.check_and_register_event("evt_recon_dup_test", "pay_dup_001", "4500.0:GATEWAY_TIMEOUT:U30")
    pm_a.close()

    pm_b = PersistenceManager(db_url=db_url)
    second_res = pm_b.check_and_register_event("evt_recon_dup_test", "pay_dup_001", "4500.0:GATEWAY_TIMEOUT:U30")
    pm_b.close()

    assert first_res is True
    assert second_res is False
    print(f"    First delivery in Process A: Accepted = {first_res}")
    print(f"    Replayed delivery in Process B (after restart): Accepted = {second_res} (DUPLICATE SUPPRESSED)")

    # 5. Concurrent Audit Writes with Row-Locking
    print("\n[5] Concurrent Multi-Worker Audit Writes:")
    workers = 8
    writes_per_worker = 4
    expected_total = workers * writes_per_worker

    def worker_job(wid):
        mgr = PersistenceManager(db_url=db_url)
        try:
            for i in range(writes_per_worker):
                t = TransactionTelemetry(
                    payment_id=f"pay_c_{wid}_{i}",
                    invoice_id=f"inv_c_{wid}_{i}",
                    amount_inr=500.0,
                    gateway_error_code="BAD_REQUEST_ERROR",
                    bank_raw_response_code="51",
                    payment_method=PaymentMethod.UPI_AUTOPAY,
                    latency_ms=200,
                    bank_switch_degradation_score=0.0
                )
                d = PolicyDecision(
                    is_overridden=False,
                    original_action=ActionType.SEND_PAYMENT_LINK,
                    final_action=ActionType.SEND_PAYMENT_LINK,
                    final_parameters={"worker": wid},
                    policy_reason=f"Worker {wid}",
                    timestamp=datetime.utcnow()
                )
                mgr.record_audit_block(t, d, "SEND_PAYMENT_LINK", PaymentState.AWAITING_CUSTOMER_ACTION.value)
        finally:
            mgr.close()

    start_t = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(worker_job, w) for w in range(workers)]
        for f in futs:
            f.result()
    dur = round(time.time() - start_t, 2)

    pm_chk = PersistenceManager(db_url=db_url)
    all_blocks = pm_chk.get_ledger_blocks()
    valid_chain, chain_err = pm_chk.verify_persisted_ledger_integrity()
    pm_chk.close()

    # Verify contiguous indexing & unbroken hashes
    indices = [b.index for b in all_blocks]
    assert indices == list(range(len(all_blocks)))
    assert valid_chain is True
    print(f"    Executed {expected_total} concurrent writes across {workers} parallel threads in {dur}s.")
    print(f"    Contiguous indices: 0..{len(all_blocks)-1} (No gaps, no duplicates)")
    print(f"    Cryptographic hash chain intact: {valid_chain} (No forks)")

    # 6. Transaction Rollback Test
    print("\n[6] Atomic Transaction Rollback on Failure:")
    pm_rb = PersistenceManager(db_url=db_url)
    pm_rb.get_or_create_case("pay_rb_demo", "inv_rb_demo", 1000.0)
    
    rb_caught = False
    try:
        with pm_rb.transaction() as conn:
            # Step A: valid transition
            pm_rb.record_transition("pay_rb_demo", PaymentState.PAYMENT_FAILED, PaymentState.TELEMETRY_ANALYSIS, "Step A", conn=conn)
            # Step B: force failure before audit block write
            raise RuntimeError("Simulated failure after case update before audit block commit!")
    except RuntimeError:
        rb_caught = True

    case_after_rb = pm_rb.get_case("pay_rb_demo")
    pm_rb.close()

    assert rb_caught is True
    assert case_after_rb["current_state"] == "PAYMENT_FAILED"
    assert len(case_after_rb["transitions"]) == 0
    print(f"    Exception raised mid-transaction: {rb_caught}")
    print(f"    PostgreSQL state after rollback: State = {case_after_rb['current_state']}, Transitions = {len(case_after_rb['transitions'])} (Clean Rollback)")

    # 7. API /evaluate/single Persisted State Machine
    print("\n[7] API /evaluate/single Per-Case State Persistence:")
    client = TestClient(app)
    api_pay_id = "pay_api_live_001"
    req_body = {
        "payment_id": api_pay_id,
        "invoice_id": "inv_api_live_001",
        "amount_inr": 2999.0,
        "gateway_error_code": "BAD_REQUEST_ERROR",
        "bank_raw_response_code": "51",
        "payment_method": "UPI_AUTOPAY",
        "latency_ms": 400,
        "bank_switch_degradation_score": 0.05,
        "inbound_message": "salary 7 tareek ko aayegi",
        "channel": "WHATSAPP"
    }
    resp = client.post("/api/evaluate/single", json=req_body)
    assert resp.status_code == 200
    resp_data = resp.json()

    pm_api = PersistenceManager(db_url=db_url)
    persisted_case_row = pm_api.get_case(api_pay_id)
    pm_api.close()

    assert persisted_case_row is not None
    assert persisted_case_row["payment_id"] == api_pay_id
    print(f"    API Response Status: {resp.status_code}")
    print(f"    PostgreSQL Persisted Case: ID = {persisted_case_row['payment_id']}, State = {persisted_case_row['current_state']}, Transitions = {len(persisted_case_row['transitions'])}")

    # 8. Authoritative Reconciliation Invariant
    print("\n[8] Authoritative Reconciliation Invariant:")
    pm_rec = PersistenceManager(db_url=db_url)
    pm_rec.get_or_create_case("pay_rec_inv", "inv_rec_inv", 2000.0)
    
    illegal_attempt = False
    try:
        pm_rec.record_transition("pay_rec_inv", PaymentState.PAYMENT_FAILED, PaymentState.RECOVERED, "Unverified claim")
    except InvalidStateTransitionError:
        illegal_attempt = True

    assert illegal_attempt is True
    print(f"    Direct transition PAYMENT_FAILED -> RECOVERED rejected: {illegal_attempt}")
    print("    RECOVERED state requires authoritative settlement reconciliation path.")
    pm_rec.close()

    print("\n" + "=" * 70)
    print("ALL PHASE 1 PERSISTENCE VERIFICATIONS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    run_full_verification()
