from __future__ import annotations
import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple
from core.schemas import AuditBlock, TransactionTelemetry, AIReasonerOutput, PolicyDecision, ExecutionResult


class AuditLedger:
    """
    Cryptographic SHA-256 Hash-Chained Immutable Audit Ledger.
    Guarantees non-repudiation and provides verifiable proof for every rupee recovered or action blocked.
    """

    GENESIS_HASH = "0" * 64

    def __init__(self):
        self.chain: List[AuditBlock] = []

    def _calculate_hash(
        self,
        index: int,
        timestamp: str,
        payment_id: str,
        telemetry_hash: str,
        ai_reasoning: Optional[Dict[str, Any]],
        policy_decision: Dict[str, Any],
        action_executed: str,
        resulting_state: str,
        previous_hash: str
    ) -> str:
        payload = {
            "index": index,
            "timestamp": timestamp,
            "payment_id": payment_id,
            "telemetry_hash": telemetry_hash,
            "ai_reasoning": ai_reasoning,
            "policy_decision": policy_decision,
            "action_executed": action_executed,
            "resulting_state": resulting_state,
            "previous_hash": previous_hash
        }
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def record_entry(
        self,
        telemetry: TransactionTelemetry,
        policy_decision: PolicyDecision,
        action_executed: str,
        resulting_state: str,
        ai_reasoning: Optional[AIReasonerOutput] = None
    ) -> AuditBlock:
        index = len(self.chain)
        prev_hash = self.chain[-1].current_hash if self.chain else self.GENESIS_HASH
        timestamp = policy_decision.timestamp.isoformat()
        
        # Calculate telemetry hash
        telem_encoded = json.dumps(telemetry.model_dump(), sort_keys=True, default=str).encode("utf-8")
        telem_hash = hashlib.sha256(telem_encoded).hexdigest()

        ai_dump = ai_reasoning.model_dump() if ai_reasoning else None
        pol_dump = policy_decision.model_dump()

        curr_hash = self._calculate_hash(
            index=index,
            timestamp=timestamp,
            payment_id=telemetry.payment_id,
            telemetry_hash=telem_hash,
            ai_reasoning=ai_dump,
            policy_decision=pol_dump,
            action_executed=action_executed,
            resulting_state=resulting_state,
            previous_hash=prev_hash
        )

        block = AuditBlock(
            index=index,
            timestamp=timestamp,
            payment_id=telemetry.payment_id,
            telemetry_hash=telem_hash,
            ai_reasoning=ai_dump,
            policy_decision=pol_dump,
            action_executed=action_executed,
            resulting_state=resulting_state,
            previous_hash=prev_hash,
            current_hash=curr_hash
        )

        self.chain.append(block)
        return block

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """
        Verifies that the hash chain is cryptographically intact and has not been tampered with.
        """
        for i, block in enumerate(self.chain):
            expected_prev = self.GENESIS_HASH if i == 0 else self.chain[i - 1].current_hash
            if block.previous_hash != expected_prev:
                return False, f"Broken link at block {i}: previous_hash mismatch"
            
            recomputed = self._calculate_hash(
                index=block.index,
                timestamp=block.timestamp,
                payment_id=block.payment_id,
                telemetry_hash=block.telemetry_hash,
                ai_reasoning=block.ai_reasoning,
                policy_decision=block.policy_decision,
                action_executed=block.action_executed,
                resulting_state=block.resulting_state,
                previous_hash=block.previous_hash
            )
            if block.current_hash != recomputed:
                return False, f"Tampered block at index {i}: hash mismatch"

        return True, None

    def export_ledger(self) -> List[Dict[str, Any]]:
        return [b.model_dump() for b in self.chain]
