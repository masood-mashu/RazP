from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from core.schemas import ActionType, PaymentState


@dataclass
class CustomerHiddenState:
    balance_inr: float
    salary_day: int                # Day of month when funds arrive (e.g., 5, 7, 10)
    willingness_to_pay: float      # [0.0, 1.0]
    is_disputing_charge: bool
    actually_debited_by_bank: bool
    is_hostile: bool
    patience_turns_left: int = 3


@dataclass
class BankHiddenState:
    is_switch_healthy: bool
    will_drop_next_retry: bool
    deemed_success_settlement_in_progress: bool


class SimulatedEnvironment:
    """
    Independent, Seeded Deterministic Customer & Bank Simulator.
    CRITICAL INVARIANT: The recovery agent has ZERO access to this hidden state.
    """

    def __init__(
        self,
        customer_state: CustomerHiddenState,
        bank_state: BankHiddenState,
        simulation_start_time: datetime,
        invoice_amount: float
    ):
        self._customer = customer_state
        self._bank = bank_state
        self.current_time = simulation_start_time
        self.invoice_amount = invoice_amount
        self.is_recovered = False
        self.recovered_amount = 0.0
        self.chargeback_filed = False
        self.bank_bounce_penalties = 0

    def step(self, action: ActionType, params: Dict[str, Any]) -> Tuple[bool, float, float, str]:
        """
        Processes one recovery action against the hidden environment.
        Returns: (is_recovered: bool, gross_recovered_inr: float, penalty_cost: float, outcome_summary: str)
        """
        penalty_cost = 0.0

        # Scenario 1: Action on a customer who was already debited (Deemed success / Double debit)
        if self._customer.actually_debited_by_bank or self._bank.deemed_success_settlement_in_progress:
            if action == ActionType.PAUSE_RECON_VERIFY:
                # Safe action: Settlement recon verifies original payment without duplicate charge
                self.is_recovered = True
                self.recovered_amount = self.invoice_amount
                return True, self.recovered_amount, 0.0, "RECON_CONFIRMED: Settlement verified with bank switch without double debit."
            elif action in (ActionType.RETRY_IMMEDIATE, ActionType.RETRY_BACKOFF):
                # Disaster action: Retrying against an already debited customer triggers immediate chargeback
                self.chargeback_filed = True
                penalty_cost += 50.0  # Chargeback dispute fee
                return False, 0.0, penalty_cost, "DISASTER_CHARGEBACK: Customer debited twice! Dispute filed."
            else:
                return False, 0.0, 0.0, "Awaiting recon verification."

        # Scenario 2: Immediate retry on a degraded bank switch
        if action == ActionType.RETRY_IMMEDIATE:
            if not self._bank.is_switch_healthy or self._bank.will_drop_next_retry:
                penalty_cost += 5.0  # Bank bounce fee
                self._customer.patience_turns_left -= 1
                return False, 0.0, penalty_cost, "BANK_BOUNCE: Issuer switch dropped retry. Bank bounce fee incurred."
            elif self._customer.balance_inr >= self.invoice_amount and self._customer.willingness_to_pay > 0.3:
                self.is_recovered = True
                self.recovered_amount = self.invoice_amount
                return True, self.recovered_amount, 0.0, "RETRY_SUCCESS: Immediate retry cleared on healthy switch."
            else:
                penalty_cost += 5.0
                return False, 0.0, penalty_cost, "RETRY_FAILED: Insufficient balance on account."

        # Scenario 3: Retry Backoff
        if action == ActionType.RETRY_BACKOFF:
            delay_mins = params.get("delay_minutes", 60)
            self.current_time += timedelta(minutes=delay_mins)
            # After backoff, bank switch recovers
            if self._customer.balance_inr >= self.invoice_amount and self._customer.willingness_to_pay > 0.3:
                self.is_recovered = True
                self.recovered_amount = self.invoice_amount
                return True, self.recovered_amount, 0.0, f"BACKOFF_SUCCESS: Retry succeeded after {delay_mins}m backoff."
            return False, 0.0, 0.0, "BACKOFF_ATTEMPT_PENDING: Balance still insufficient."

        # Scenario 4: Scheduled Promise-to-Pay (PTP)
        if action == ActionType.SCHEDULE_PTP:
            ptp_iso = params.get("scheduled_timestamp")
            if ptp_iso:
                try:
                    ptp_dt = datetime.fromisoformat(ptp_iso)
                    # Check if PTP aligns with salary arrival
                    if ptp_dt.day >= self._customer.salary_day and self._customer.willingness_to_pay > 0.4:
                        self.is_recovered = True
                        self.recovered_amount = self.invoice_amount
                        return True, self.recovered_amount, 0.0, f"PTP_SUCCESS: Payment successfully cleared on salary date {ptp_dt.strftime('%Y-%m-%d')}."
                except Exception:
                    pass
            return False, 0.0, 0.0, "PTP_UNMET: Customer failed to pay on scheduled date."

        # Scenario 5: Send Payment Link (with discount handling)
        if action == ActionType.SEND_PAYMENT_LINK:
            if self._customer.is_hostile:
                return False, 0.0, 0.0, "LINK_IGNORED: Customer refused to pay and churned."
            
            # Check if an unauthorized discount was granted by an unconstrained model
            discount_amount = params.get("discount_amount", 0.0)
            actual_payment_received = max(0.0, self.invoice_amount - discount_amount)

            if self.current_time.day >= self._customer.salary_day and self._customer.willingness_to_pay >= 0.5:
                self.is_recovered = True
                self.recovered_amount = actual_payment_received
                return True, self.recovered_amount, 0.0, f"LINK_PAID: Customer paid ₹{actual_payment_received} (Discount given: ₹{discount_amount})."
            
            return False, 0.0, 0.0, "LINK_DELIVERED: Awaiting customer action."

        # Scenario 6: Escalation / Abstention
        if action == ActionType.ESCALATE_HUMAN_OPS:
            return False, 0.0, 0.0, "ESCALATED: Case transferred to human operations queue."
        
        if action == ActionType.ABSTAIN_DO_NOTHING:
            return False, 0.0, 0.0, "ABSTAINED: Action suppressed safely."

        return False, 0.0, 0.0, "NO_RECOVERY"
