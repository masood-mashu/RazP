from __future__ import annotations
import hashlib
from typing import Set, Dict, Tuple, Optional
from core.schemas import PaymentState, ActionType


class InvalidStateTransitionError(Exception):
    pass


class IdempotentDuplicateEventError(Exception):
    pass


class StateMachine:
    """
    Deterministic Finite State Machine governing recovery lifecycles.
    Enforces strict transition validation, idempotency checks, and prevents unauthorized state jumps.
    """

    VALID_TRANSITIONS: Dict[PaymentState, Set[PaymentState]] = {
        PaymentState.PAYMENT_FAILED: {
            PaymentState.TELEMETRY_ANALYSIS,
            PaymentState.DEAD_LETTER,
            PaymentState.ESCALATED_HUMAN_OPS
        },
        PaymentState.TELEMETRY_ANALYSIS: {
            PaymentState.DEDUCTION_SUSPECTED,
            PaymentState.POLICY_GATED,
            PaymentState.ESCALATED_HUMAN_OPS,
            PaymentState.DEAD_LETTER
        },
        PaymentState.DEDUCTION_SUSPECTED: {
            PaymentState.PAUSE_RECON_VERIFY
        },
        PaymentState.PAUSE_RECON_VERIFY: {
            PaymentState.RECOVERED,
            PaymentState.TELEMETRY_ANALYSIS,
            PaymentState.ESCALATED_HUMAN_OPS,
            PaymentState.DEAD_LETTER
        },
        PaymentState.POLICY_GATED: {
            PaymentState.RETRY_SCHEDULED,
            PaymentState.PTP_SCHEDULED,
            PaymentState.AWAITING_CUSTOMER_ACTION,
            PaymentState.PAUSE_RECON_VERIFY,
            PaymentState.ESCALATED_HUMAN_OPS,
            PaymentState.DEAD_LETTER,
            PaymentState.RECOVERED
        },
        PaymentState.RETRY_SCHEDULED: {
            PaymentState.PAYMENT_FAILED,
            PaymentState.RECOVERED,
            PaymentState.DEAD_LETTER
        },
        PaymentState.PTP_SCHEDULED: {
            PaymentState.RETRY_SCHEDULED,
            PaymentState.AWAITING_CUSTOMER_ACTION,
            PaymentState.PAYMENT_FAILED,
            PaymentState.RECOVERED,
            PaymentState.DEAD_LETTER
        },
        PaymentState.AWAITING_CUSTOMER_ACTION: {
            PaymentState.RECOVERED,
            PaymentState.TELEMETRY_ANALYSIS,
            PaymentState.PAYMENT_FAILED,
            PaymentState.DEAD_LETTER
        },
        # Terminal States
        PaymentState.RECOVERED: set(),
        PaymentState.DEAD_LETTER: set(),
        PaymentState.ESCALATED_HUMAN_OPS: set()
    }

    ACTION_TARGET_STATE_MAP: Dict[ActionType, PaymentState] = {
        ActionType.RETRY_IMMEDIATE: PaymentState.RETRY_SCHEDULED,
        ActionType.RETRY_BACKOFF: PaymentState.RETRY_SCHEDULED,
        ActionType.SEND_PAYMENT_LINK: PaymentState.AWAITING_CUSTOMER_ACTION,
        ActionType.SCHEDULE_PTP: PaymentState.PTP_SCHEDULED,
        ActionType.PAUSE_RECON_VERIFY: PaymentState.PAUSE_RECON_VERIFY,
        ActionType.ESCALATE_HUMAN_OPS: PaymentState.ESCALATED_HUMAN_OPS,
        ActionType.ABSTAIN_DO_NOTHING: PaymentState.DEAD_LETTER
    }

    def __init__(self, initial_state: PaymentState = PaymentState.PAYMENT_FAILED):
        self._current_state = initial_state
        self._transition_history: list[Tuple[PaymentState, PaymentState, str]] = []
        self._processed_event_hashes: Set[str] = set()

    @property
    def current_state(self) -> PaymentState:
        return self._current_state

    def is_terminal(self) -> bool:
        return self._current_state in (
            PaymentState.RECOVERED,
            PaymentState.DEAD_LETTER,
            PaymentState.ESCALATED_HUMAN_OPS
        )

    def check_and_register_event(self, event_id: str, payload_str: str) -> bool:
        """
        Idempotency Guard: Returns False if event hash has already been processed.
        Prevents duplicate action dispatches on replayed webhooks.
        """
        event_hash = hashlib.sha256(f"{event_id}:{payload_str}".encode("utf-8")).hexdigest()
        if event_hash in self._processed_event_hashes:
            return False
        self._processed_event_hashes.add(event_hash)
        return True

    def transition(self, to_state: PaymentState, reason: str = "") -> PaymentState:
        """
        Deterministically transitions to target state if valid.
        Raises InvalidStateTransitionError if transition is illegal.
        """
        if self.is_terminal():
            raise InvalidStateTransitionError(
                f"Cannot transition out of terminal state {self._current_state.value}. Attempted transition to {to_state.value}."
            )

        allowed = self.VALID_TRANSITIONS.get(self._current_state, set())
        if to_state not in allowed:
            raise InvalidStateTransitionError(
                f"Illegal state transition from {self._current_state.value} to {to_state.value}. Reason: {reason}"
            )
        
        from_state = self._current_state
        self._current_state = to_state
        self._transition_history.append((from_state, to_state, reason))
        return self._current_state

    def get_target_state_for_action(self, action: ActionType) -> PaymentState:
        return self.ACTION_TARGET_STATE_MAP[action]

    def get_history(self) -> list[Tuple[PaymentState, PaymentState, str]]:
        return list(self._transition_history)
