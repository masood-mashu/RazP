"""
RazP In-Memory Engine for Non-Production & Local Demonstration.
Provides thread-safe per-payment state machine isolation, per-payment idempotency tracking,
bounded memory cleanup, and ledger synchronization.

WARNING: In-memory mode is strictly NON-DURABLE. State is lost on process restart.
"""

from __future__ import annotations
import time
import hashlib
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

from core.schemas import PaymentState, TransactionTelemetry, PolicyDecision, ActionType, AIReasonerOutput, AuditBlock
from core.state_machine import StateMachine, InvalidStateTransitionError
from core.ledger import AuditLedger
from core.persistence import EventReservationStatus


class InMemoryEngine:
    """
    Thread-safe, bounded in-memory simulation engine ensuring complete isolation
    between individual payment cases.
    """
    NON_DURABLE_WARNING = (
        "WARNING: RazP is operating in EPHEMERAL IN-MEMORY mode. "
        "Audit blocks, cases, and transitions are NOT durably persisted to PostgreSQL "
        "and will be discarded upon server restart."
    )

    def __init__(self, max_cases: int = 1000):
        self.lock = threading.RLock()
        self.max_cases = max_cases
        # payment_id -> StateMachine (OrderedDict for LRU/FIFO eviction)
        self._state_machines: OrderedDict[str, StateMachine] = OrderedDict()
        # payment_id -> case metadata dict
        self._cases: OrderedDict[str, dict] = OrderedDict()
        # (event_id, payment_id) -> event record dict
        self._events: OrderedDict[Tuple[str, str], dict] = OrderedDict()
        # Synchronized audit ledger
        self.ledger = AuditLedger()

    def _prune_if_needed(self):
        """Maintains bounded memory footprint under continuous traffic."""
        while len(self._cases) >= self.max_cases:
            oldest_id, _ = self._cases.popitem(last=False)
            self._state_machines.pop(oldest_id, None)
        while len(self._events) >= self.max_cases * 2:
            self._events.popitem(last=False)

    def get_or_create_case(
        self,
        payment_id: str,
        invoice_id: str = "",
        amount_inr: float = 0.0,
        initial_state: PaymentState = PaymentState.PAYMENT_FAILED
    ) -> Tuple[StateMachine, dict]:
        with self.lock:
            self._prune_if_needed()
            if payment_id not in self._state_machines:
                sm = StateMachine(initial_state=initial_state)
                self._state_machines[payment_id] = sm
                self._cases[payment_id] = {
                    "payment_id": payment_id,
                    "invoice_id": invoice_id or f"inv_{payment_id}",
                    "amount_inr": amount_inr,
                    "current_state": sm.current_state.value,
                    "attempt_count": 1,
                    "contact_count": 0,
                    "is_terminal": False,
                    "recovered_amount": 0.0,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "transitions": []
                }
            else:
                sm = self._state_machines[payment_id]
                # Update details if provided
                if amount_inr > 0:
                    self._cases[payment_id]["amount_inr"] = amount_inr
                if invoice_id:
                    self._cases[payment_id]["invoice_id"] = invoice_id
            return sm, self._cases[payment_id]

    def get_case(self, payment_id: str) -> Optional[dict]:
        with self.lock:
            case = self._cases.get(payment_id)
            if not case:
                return None
            return dict(case)

    def list_cases(self, limit: int = 50, offset: int = 0) -> List[dict]:
        with self.lock:
            all_cases = list(self._cases.values())
            return all_cases[offset:offset + limit]

    def load_state_machine(self, payment_id: str) -> StateMachine:
        with self.lock:
            case = self._cases.get(payment_id)
            if not case:
                return StateMachine(initial_state=PaymentState.PAYMENT_FAILED)
            sm = StateMachine(initial_state=PaymentState(case["current_state"]))
            sm._transition_history = [
                (PaymentState(t["from_state"]), PaymentState(t["to_state"]), t["reason"])
                for t in case.get("transitions", [])
            ]
            return sm

    def record_transition(
        self,
        payment_id: str,
        from_state: PaymentState,
        to_state: PaymentState,
        reason: str
    ) -> dict:
        """
        Records an isolated transition for the target payment, strictly validating
        that caller's from_state matches the payment's actual current state.
        """
        with self.lock:
            _, case = self.get_or_create_case(payment_id)
            if case["current_state"] != from_state.value:
                raise InvalidStateTransitionError(
                    f"State conflict on case {payment_id}: expected current state '{case['current_state']}', "
                    f"but caller specified from_state '{from_state.value}'."
                )

            allowed = StateMachine.VALID_TRANSITIONS.get(PaymentState(case["current_state"]), set())
            if to_state not in allowed:
                raise InvalidStateTransitionError(
                    f"Illegal state transition from {case['current_state']} to {to_state.value}. Reason: {reason}"
                )

            is_term = to_state in (PaymentState.RECOVERED, PaymentState.DEAD_LETTER)
            case["current_state"] = to_state.value
            case["is_terminal"] = is_term
            case["updated_at"] = datetime.now(timezone.utc).isoformat()
            case["transitions"].append({
                "from_state": from_state.value,
                "to_state": to_state.value,
                "reason": reason,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            if payment_id in self._state_machines:
                self._state_machines[payment_id]._current_state = to_state
                self._state_machines[payment_id]._transition_history.append((from_state, to_state, reason))
            return dict(case)

    def mark_case_recovered(self, payment_id: str, settled_amount: float, rrn: str) -> dict:
        """
        Authoritative bank reconciliation state transition for a payment case.
        """
        with self.lock:
            sm, case = self.get_or_create_case(payment_id)
            prev_st = case["current_state"]
            sm.transition(PaymentState.RECOVERED, f"Bank reconciliation confirmed RRN {rrn}")
            case["current_state"] = PaymentState.RECOVERED.value
            case["is_terminal"] = True
            case["recovered_amount"] = round(settled_amount, 2)
            case["rrn"] = rrn
            case["updated_at"] = datetime.now(timezone.utc).isoformat()
            case["transitions"].append({
                "from_state": prev_st,
                "to_state": PaymentState.RECOVERED.value,
                "reason": f"Bank reconciliation confirmed RRN {rrn} (Amount: INR {settled_amount})",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            return dict(case)

    def reserve_event(
        self,
        event_id: str,
        payment_id: str,
        payload_str: str
    ) -> EventReservationStatus:
        """
        Two-phase idempotency reservation for in-memory execution.
        """
        with self.lock:
            self._prune_if_needed()
            key = (event_id, payment_id)
            now = time.time()
            payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

            if key in self._events:
                ev = self._events[key]
                if ev["status"] == "PROCESSED":
                    return EventReservationStatus.ALREADY_PROCESSED
                elif ev["status"] == "FAILED":
                    ev["status"] = "PENDING"
                    ev["timestamp"] = now
                    ev["payload_hash"] = payload_hash
                    return EventReservationStatus.RETRY_RESERVED
                else:  # PENDING
                    # Check in-flight expiration (60s lease)
                    if now - ev["timestamp"] > 60.0:
                        ev["timestamp"] = now
                        return EventReservationStatus.RETRY_RESERVED
                    return EventReservationStatus.IN_FLIGHT

            self._events[key] = {
                "status": "PENDING",
                "payload_hash": payload_hash,
                "timestamp": now,
                "error": None
            }
            return EventReservationStatus.NEW_RESERVED

    def complete_event(self, event_id: str, payment_id: str):
        with self.lock:
            key = (event_id, payment_id)
            if key in self._events:
                self._events[key]["status"] = "PROCESSED"
                self._events[key]["timestamp"] = time.time()

    def release_event_reservation(self, event_id: str, payment_id: str, error_msg: str = ""):
        with self.lock:
            key = (event_id, payment_id)
            if key in self._events:
                self._events[key]["status"] = "FAILED"
                self._events[key]["error"] = error_msg
                self._events[key]["timestamp"] = time.time()

    def record_audit_block(
        self,
        telemetry: TransactionTelemetry,
        policy_decision: PolicyDecision,
        action_executed: str,
        resulting_state: str,
        ai_reasoning: Optional[AIReasonerOutput] = None,
        correlation_id: Optional[str] = None,
        actor_id: Optional[str] = None
    ) -> AuditBlock:
        with self.lock:
            return self.ledger.record_entry(
                telemetry=telemetry,
                policy_decision=policy_decision,
                action_executed=action_executed,
                resulting_state=resulting_state,
                ai_reasoning=ai_reasoning
            )
