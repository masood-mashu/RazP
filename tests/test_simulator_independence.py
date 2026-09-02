import pytest
from datetime import datetime
from core.schemas import TransactionTelemetry, PaymentMethod, ActionType
from simulator.environment import (
    SimulatedEnvironment,
    CustomerHiddenState,
    BankHiddenState
)
from core.reasoner import AIReasoner


def test_telemetry_schema_has_no_hidden_simulator_state():
    """
    CRITICAL INVARIANT: The TransactionTelemetry schema consumed by the AI
    and Policy Gate cannot contain or expose hidden environment variables.
    """
    fields = set(TransactionTelemetry.model_fields.keys())
    
    hidden_forbidden_fields = {
        "balance_inr",
        "salary_day",
        "willingness_to_pay",
        "is_disputing_charge",
        "actually_debited_by_bank",
        "is_hostile",
        "is_switch_healthy",
        "will_drop_next_retry",
        "deemed_success_settlement_in_progress"
    }
    
    overlap = fields.intersection(hidden_forbidden_fields)
    assert len(overlap) == 0, f"Leaked hidden simulator state into telemetry schema: {overlap}"


def test_simulator_deterministic_seeded_reproducibility():
    """
    CRITICAL INVARIANT: The environment simulator produces 100% reproducible
    step outcomes given identical initial states and actions.
    """
    start_time = datetime(2026, 9, 1, 14, 0, 0)
    
    def run_sim():
        cust = CustomerHiddenState(
            balance_inr=1000.0,
            salary_day=7,
            willingness_to_pay=0.8,
            is_disputing_charge=False,
            actually_debited_by_bank=False,
            is_hostile=False
        )
        bank = BankHiddenState(
            is_switch_healthy=True,
            will_drop_next_retry=False,
            deemed_success_settlement_in_progress=False
        )
        env = SimulatedEnvironment(cust, bank, start_time, 1500.0)
        return env.step(ActionType.SCHEDULE_PTP, {"scheduled_timestamp": "2026-09-07T10:00:00"})

    res1 = run_sim()
    res2 = run_sim()
    
    assert res1 == res2
    assert res1[0] is True # Successfully recovered on salary date
    assert res1[1] == 1500.0 # Exact invoice amount recovered


def test_agent_cannot_mutate_hidden_simulator_state():
    """
    CRITICAL INVARIANT: An adversarial agent cannot pass params to alter
    hidden simulator variables (e.g. attempting to force actually_debited_by_bank=False).
    """
    cust = CustomerHiddenState(
        balance_inr=0.0,
        salary_day=15,
        willingness_to_pay=0.1,
        is_disputing_charge=True,
        actually_debited_by_bank=True,
        is_hostile=True
    )
    bank = BankHiddenState(
        is_switch_healthy=False,
        will_drop_next_retry=True,
        deemed_success_settlement_in_progress=True
    )
    env = SimulatedEnvironment(cust, bank, datetime.utcnow(), 2000.0)
    
    # Adversarial action payload attempting to inject hidden state overrides
    is_rec, gross, penalty, msg = env.step(
        ActionType.RETRY_IMMEDIATE,
        params={"actually_debited_by_bank": False, "willingness_to_pay": 1.0}
    )
    
    # Environment ignores malicious parameter injection and detects double debit attempt!
    assert is_rec is False
    assert env.chargeback_filed is True
    assert penalty == 50.0 # Incurred dispute penalty
    assert "DISASTER_CHARGEBACK" in msg
