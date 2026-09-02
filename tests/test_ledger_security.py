from datetime import datetime
from core.schemas import (
    TransactionTelemetry,
    PolicyDecision,
    ActionType,
    PaymentMethod,
    PaymentState
)
from core.ledger import AuditLedger


def create_sample_block_data(payment_id: str):
    telem = TransactionTelemetry(
        payment_id=payment_id,
        invoice_id=f"inv_{payment_id}",
        amount_inr=1000.0,
        gateway_error_code="GATEWAY_ERROR",
        bank_raw_response_code="91",
        payment_method=PaymentMethod.CARD_MANDATE,
        latency_ms=800,
        bank_switch_degradation_score=0.3
    )
    decision = PolicyDecision(
        is_overridden=False,
        original_action=ActionType.RETRY_BACKOFF,
        final_action=ActionType.RETRY_BACKOFF,
        final_parameters={"delay_minutes": 30},
        violations_detected=[],
        policy_reason="Standard bank retry backoff"
    )
    return telem, decision


def test_ledger_detects_block_reordering():
    ledger = AuditLedger()
    
    # Record 3 blocks
    for i in range(3):
        t, d = create_sample_block_data(f"pay_sec_{i}")
        ledger.record_entry(t, d, "RETRY_BACKOFF", PaymentState.RETRY_SCHEDULED.value)
    
    is_valid, err = ledger.verify_integrity()
    assert is_valid is True
    
    # Swap block 1 and block 2
    ledger.chain[1], ledger.chain[2] = ledger.chain[2], ledger.chain[1]
    
    is_valid_swapped, err_swapped = ledger.verify_integrity()
    assert is_valid_swapped is False
    assert "Broken link at block 1" in err_swapped or "Tampered block at index 1" in err_swapped


def test_ledger_detects_monetary_tampering():
    ledger = AuditLedger()
    t, d = create_sample_block_data("pay_tamper_amt")
    ledger.record_entry(t, d, "RETRY_BACKOFF", PaymentState.RETRY_SCHEDULED.value)
    
    assert ledger.verify_integrity()[0] is True
    
    # Adversary attempts to alter telemetry hash or action executed
    ledger.chain[0].action_executed = "UNAUTHORIZED_TRANSFER_99999"
    is_valid, err = ledger.verify_integrity()
    assert is_valid is False
    assert "Tampered block at index 0" in err


def test_ledger_genesis_hash_immutable():
    ledger = AuditLedger()
    t, d = create_sample_block_data("pay_genesis_check")
    ledger.record_entry(t, d, "RETRY_BACKOFF", PaymentState.RETRY_SCHEDULED.value)
    
    assert ledger.chain[0].previous_hash == AuditLedger.GENESIS_HASH
    
    # Alter genesis hash
    ledger.chain[0].previous_hash = "1" * 64
    is_valid, err = ledger.verify_integrity()
    assert is_valid is False
    assert "Broken link at block 0" in err
