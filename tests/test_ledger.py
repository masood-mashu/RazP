from datetime import datetime
from core.schemas import (
    TransactionTelemetry,
    AIReasonerOutput,
    PolicyDecision,
    ActionType,
    RootCauseCategory,
    CustomerIntentCategory,
    PaymentMethod,
    PaymentState
)
from core.ledger import AuditLedger


def test_audit_ledger_integrity_and_tamper_detection():
    ledger = AuditLedger()
    
    telemetry = TransactionTelemetry(
        payment_id="pay_audit_1",
        invoice_id="inv_audit_1",
        amount_inr=999.0,
        gateway_error_code="GATEWAY_ERROR",
        bank_raw_response_code="91",
        payment_method=PaymentMethod.CARD_MANDATE,
        latency_ms=1200,
        bank_switch_degradation_score=0.4
    )
    
    decision = PolicyDecision(
        is_overridden=False,
        original_action=ActionType.RETRY_BACKOFF,
        final_action=ActionType.RETRY_BACKOFF,
        final_parameters={"delay_minutes": 30},
        violations_detected=[],
        policy_reason="Standard bank retry backoff applied"
    )
    
    # Record 2 blocks
    b1 = ledger.record_entry(
        telemetry=telemetry,
        policy_decision=decision,
        action_executed="RETRY_BACKOFF",
        resulting_state=PaymentState.RETRY_SCHEDULED.value
    )
    
    b2 = ledger.record_entry(
        telemetry=telemetry,
        policy_decision=decision,
        action_executed="PAYMENT_SUCCESS",
        resulting_state=PaymentState.RECOVERED.value
    )
    
    assert len(ledger.chain) == 2
    is_valid, err = ledger.verify_integrity()
    assert is_valid is True
    assert err is None
    
    # Now tamper with block 1
    ledger.chain[0].action_executed = "TAMPERED_ACTION"
    is_valid_tampered, err_tampered = ledger.verify_integrity()
    assert is_valid_tampered is False
    assert "Tampered block at index 0" in err_tampered
