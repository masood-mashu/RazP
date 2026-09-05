"""
RazP PostgreSQL Durable Persistence Layer.
Provides transaction-safe storage for:
- Case lifecycle state and full transition history
- Webhook deduplication and event idempotency hashes
- Cryptographic SHA-256 hash-chained audit ledger blocks (with concurrent row-locking)
- Runtime-configurable merchant policies
"""
from __future__ import annotations

import os
import json
import hashlib
from datetime import datetime, time
from contextlib import contextmanager
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor, Json
    PSYCOPG2_AVAILABLE = True
except Exception:
    psycopg2 = None
    pool = None
    RealDictCursor = None
    Json = None
    PSYCOPG2_AVAILABLE = False

from core.schemas import (
    PaymentState,
    ActionType,
    AuditBlock,
    MerchantPolicy,
    TransactionTelemetry,
    PolicyDecision,
    AIReasonerOutput,
)
from core.state_machine import StateMachine, InvalidStateTransitionError
from core.ledger import AuditLedger


class PersistenceError(Exception):
    """Base exception for persistence errors."""
    pass


class CaseNotFoundError(PersistenceError):
    """Raised when a queried payment case does not exist."""
    pass


class DuplicateEventError(PersistenceError):
    """Raised when an event has already been processed (idempotency rejection)."""
    pass


class PersistenceManager:
    """
    Thread-safe PostgreSQL persistence manager with connection pooling and
    transaction-isolated operations.
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        min_conn: int = 1,
        max_conn: int = 10
    ):
        if not PSYCOPG2_AVAILABLE:
            raise PersistenceError(
                "psycopg2 is not available in the current runtime environment. "
                "Set RAZP_DEMO_IN_MEMORY=true or install psycopg2-binary with required C libraries."
            )
        raw_url = db_url or os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("POSTGRES_PRISMA_URL") or os.getenv("SUPABASE_DATABASE_URL")
        if raw_url and raw_url.startswith("postgres://"):
            raw_url = "postgresql://" + raw_url[len("postgres://"):]
        self.db_url = raw_url
        if not self.db_url:
            raise PersistenceError(
                "DATABASE_URL (or POSTGRES_URL) is not set. Please provide a valid PostgreSQL connection string."
            )
        
        try:
            self._pool = pool.ThreadedConnectionPool(
                minconn=min_conn,
                maxconn=max_conn,
                dsn=self.db_url
            )
        except Exception as exc:
            raise PersistenceError(f"Failed to initialize PostgreSQL connection pool: {exc}") from exc

    def close(self):
        """Closes all connections in the pool."""
        if hasattr(self, "_pool") and self._pool is not None:
            self._pool.closeall()

    @contextmanager
    def get_connection(self):
        """Context manager to check out and return a connection from the pool."""
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    @contextmanager
    def transaction(self, existing_conn=None):
        """
        Context manager for an atomic database transaction.
        Rolls back on exception and commits on success.
        """
        if existing_conn is not None:
            # Nested within existing connection/transaction
            yield existing_conn
        else:
            with self.get_connection() as conn:
                try:
                    conn.autocommit = False
                    yield conn
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise

    # =========================================================================
    # 1. Payment Cases & Transition History
    # =========================================================================

    def get_or_create_case(
        self,
        payment_id: str,
        invoice_id: str,
        amount_inr: float,
        initial_state: PaymentState = PaymentState.PAYMENT_FAILED,
        attempt_count: int = 1,
        conn=None
    ) -> Dict[str, Any]:
        """
        Retrieves an existing case or creates a new one inside a transaction.
        """
        with self.transaction(conn) as tx:
            with tx.cursor(cursor_factory=RealDictCursor) as cur:
                # Lock row if exists for atomic updates
                cur.execute(
                    "SELECT * FROM payment_cases WHERE payment_id = %s FOR UPDATE;",
                    (payment_id,)
                )
                row = cur.fetchone()
                if row:
                    return dict(row)

                is_term = initial_state in (
                    PaymentState.RECOVERED,
                    PaymentState.DEAD_LETTER
                )
                cur.execute(
                    """
                    INSERT INTO payment_cases (
                        payment_id, invoice_id, amount_inr, current_state,
                        attempt_count, contact_count, is_terminal, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING *;
                    """,
                    (
                        payment_id,
                        invoice_id,
                        amount_inr,
                        initial_state.value,
                        attempt_count,
                        0,
                        is_term
                    )
                )
                new_case = cur.fetchone()
                return dict(new_case)

    def list_cases(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        conn=None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves a paginated and filterable list of payment cases.
        """
        with self.transaction(conn) as tx:
            with tx.cursor(cursor_factory=RealDictCursor) as cur:
                query = "SELECT * FROM payment_cases WHERE 1=1"
                params: List[Any] = []

                if status and status != "ALL":
                    query += " AND current_state = %s"
                    params.append(status)

                if search:
                    query += " AND (payment_id ILIKE %s OR invoice_id ILIKE %s)"
                    search_pat = f"%{search}%"
                    params.extend([search_pat, search_pat])

                query += " ORDER BY updated_at DESC LIMIT %s OFFSET %s;"
                params.extend([limit, offset])

                cur.execute(query, params)
                return [dict(r) for r in cur.fetchall()]

    def get_dashboard_stats(self, conn=None) -> Dict[str, Any]:
        """
        Computes real-time aggregated financial recovery metrics from PostgreSQL.
        """
        with self.transaction(conn) as tx:
            with tx.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total_cases,
                        COUNT(*) FILTER (WHERE is_terminal = FALSE) AS active_cases,
                        COUNT(*) FILTER (WHERE current_state = 'RECOVERED') AS recovered_cases,
                        COUNT(*) FILTER (WHERE current_state = 'ESCALATED_HUMAN_OPS') AS escalated_cases,
                        COUNT(*) FILTER (WHERE current_state = 'DEAD_LETTER') AS dead_letter_cases,
                        COALESCE(SUM(amount_inr) FILTER (WHERE is_terminal = FALSE), 0) AS revenue_at_risk,
                        COALESCE(SUM(amount_inr) FILTER (WHERE current_state = 'RECOVERED'), 0) AS recovered_revenue,
                        COALESCE(SUM(amount_inr), 0) AS total_exposure
                    FROM payment_cases;
                    """
                )
                row = cur.fetchone()
                total_exp = float(row["total_exposure"])
                rec_rev = float(row["recovered_revenue"])
                recovery_yield = round((rec_rev / total_exp * 100.0), 2) if total_exp > 0 else 0.0

                return {
                    "total_cases": int(row["total_cases"]),
                    "active_cases": int(row["active_cases"]),
                    "recovered_cases": int(row["recovered_cases"]),
                    "escalated_cases": int(row["escalated_cases"]),
                    "dead_letter_cases": int(row["dead_letter_cases"]),
                    "revenue_at_risk": float(row["revenue_at_risk"]),
                    "recovered_revenue": rec_rev,
                    "total_exposure": total_exp,
                    "recovery_yield_pct": recovery_yield
                }

    def get_case(self, payment_id: str, conn=None) -> Optional[Dict[str, Any]]:
        """
        Retrieves case metadata along with its complete ordered transition history.
        """
        with self.transaction(conn) as tx:
            with tx.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM payment_cases WHERE payment_id = %s;", (payment_id,))
                case_row = cur.fetchone()
                if not case_row:
                    return None

                cur.execute(
                    """
                    SELECT from_state, to_state, reason, transition_order, created_at
                    FROM state_transitions
                    WHERE payment_id = %s
                    ORDER BY transition_order ASC;
                    """,
                    (payment_id,)
                )
                transitions = [dict(t) for t in cur.fetchall()]
                result = dict(case_row)
                result["transitions"] = transitions
                return result

    def record_transition(
        self,
        payment_id: str,
        from_state: PaymentState,
        to_state: PaymentState,
        reason: str = "",
        conn=None
    ) -> Dict[str, Any]:
        """
        Validates and records a state transition. Enforces terminal immutability
        and state-machine validity rules directly in PostgreSQL.
        """
        with self.transaction(conn) as tx:
            with tx.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT current_state, is_terminal, attempt_count, contact_count FROM payment_cases WHERE payment_id = %s FOR UPDATE;",
                    (payment_id,)
                )
                row = cur.fetchone()
                if not row:
                    raise CaseNotFoundError(f"Case {payment_id} does not exist.")

                curr_state_val = row["current_state"]
                if from_state.value != curr_state_val:
                    raise InvalidStateTransitionError(
                        f"State conflict on case {payment_id}: database current state is '{curr_state_val}', "
                        f"but caller attempted transition from '{from_state.value}'."
                    )
                if row["is_terminal"]:
                    raise InvalidStateTransitionError(
                        f"Cannot transition out of terminal state {curr_state_val}. Attempted transition to {to_state.value}."
                    )

                allowed_transitions = StateMachine.VALID_TRANSITIONS.get(PaymentState(curr_state_val), set())
                if to_state not in allowed_transitions:
                    raise InvalidStateTransitionError(
                        f"Illegal state transition from {curr_state_val} to {to_state.value}. Reason: {reason}"
                    )

                # Determine next transition order index
                cur.execute(
                    "SELECT COALESCE(MAX(transition_order), 0) + 1 AS next_order FROM state_transitions WHERE payment_id = %s;",
                    (payment_id,)
                )
                next_order = cur.fetchone()["next_order"]

                # Insert state transition history record
                cur.execute(
                    """
                    INSERT INTO state_transitions (
                        payment_id, from_state, to_state, reason, transition_order, created_at
                    ) VALUES (%s, %s, %s, %s, %s, NOW());
                    """,
                    (payment_id, from_state.value, to_state.value, reason, next_order)
                )

                is_term = to_state in (
                    PaymentState.RECOVERED,
                    PaymentState.DEAD_LETTER
                )

                # Update payment_cases row
                cur.execute(
                    """
                    UPDATE payment_cases
                    SET current_state = %s,
                        is_terminal = %s,
                        updated_at = NOW()
                    WHERE payment_id = %s
                    RETURNING *;
                    """,
                    (to_state.value, is_term, payment_id)
                )
                updated_case = cur.fetchone()
                return dict(updated_case)

    def load_state_machine(self, payment_id: str, conn=None) -> StateMachine:
        """
        Hydrates an in-memory StateMachine instance from PostgreSQL state and history.
        """
        case_data = self.get_case(payment_id, conn=conn)
        if not case_data:
            raise CaseNotFoundError(f"Payment case {payment_id} not found in database.")

        sm = StateMachine(initial_state=PaymentState(case_data["current_state"]))
        # Reconstruct transitions history
        sm._transition_history = [
            (PaymentState(t["from_state"]), PaymentState(t["to_state"]), t["reason"])
            for t in case_data.get("transitions", [])
        ]
        return sm

class EventReservationStatus(str, Enum):
    NEW_RESERVED = "NEW_RESERVED"
    ALREADY_PROCESSED = "ALREADY_PROCESSED"
    IN_FLIGHT = "IN_FLIGHT"
    RETRY_RESERVED = "RETRY_RESERVED"


    # =========================================================================
    # 2. Processed Events / Two-Phase Idempotency Protection
    # =========================================================================

    def reserve_event(
        self,
        event_id: str,
        payment_id: str,
        payload_str: str,
        conn=None
    ) -> EventReservationStatus:
        """
        Two-Phase Idempotency Phase 1:
        Atomically attempts to reserve an event reservation BEFORE long LLM reasoning.
        Returns:
          - NEW_RESERVED: Successfully reserved pending execution.
          - ALREADY_PROCESSED: Event was already committed previously; suppress replay.
          - IN_FLIGHT: Another worker is actively processing this event.
          - RETRY_RESERVED: Previous attempt failed; retry reservation granted.
        """
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        event_hash = hashlib.sha256(f"{event_id}:{payload_str}".encode("utf-8")).hexdigest()

        with self.transaction(conn) as tx:
            with tx.cursor(cursor_factory=RealDictCursor) as cur:
                # Check for existing record
                cur.execute(
                    """
                    SELECT event_hash, status, first_processed_at 
                    FROM processed_events 
                    WHERE event_id = %s AND payment_id = %s;
                    """,
                    (event_id, payment_id)
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        """
                        INSERT INTO processed_events (
                            event_hash, event_id, payment_id, payload_hash, first_processed_at, status
                        ) VALUES (%s, %s, %s, %s, NOW(), 'PENDING')
                        ON CONFLICT (event_id, payment_id) DO NOTHING
                        RETURNING event_hash;
                        """,
                        (event_hash, event_id, payment_id, payload_hash)
                    )
                    inserted = cur.fetchone()
                    if inserted:
                        return EventReservationStatus.NEW_RESERVED

                    cur.execute(
                        "SELECT status, first_processed_at FROM processed_events WHERE event_id = %s AND payment_id = %s;",
                        (event_id, payment_id)
                    )
                    row = cur.fetchone()

                curr_status = row.get("status", "PROCESSED") if row else "PROCESSED"
                if curr_status == "PROCESSED":
                    return EventReservationStatus.ALREADY_PROCESSED
                elif curr_status == "FAILED":
                    cur.execute(
                        """
                        UPDATE processed_events 
                        SET status = 'PENDING', payload_hash = %s, updated_at = NOW() 
                        WHERE event_id = %s AND payment_id = %s;
                        """,
                        (payload_hash, event_id, payment_id)
                    )
                    return EventReservationStatus.RETRY_RESERVED
                else:  # PENDING
                    return EventReservationStatus.IN_FLIGHT

    def complete_event(self, event_id: str, payment_id: str, conn=None) -> None:
        """
        Two-Phase Idempotency Phase 2 (Success):
        Marks reserved event as permanently PROCESSED in the same transaction as state/ledger persistence.
        """
        with self.transaction(conn) as tx:
            with tx.cursor() as cur:
                cur.execute(
                    """
                    UPDATE processed_events 
                    SET status = 'PROCESSED', updated_at = NOW() 
                    WHERE event_id = %s AND payment_id = %s;
                    """,
                    (event_id, payment_id)
                )

    def release_event_reservation(self, event_id: str, payment_id: str, error_msg: str = "", conn=None) -> None:
        """
        Two-Phase Idempotency Phase 2 (Failure):
        Marks event reservation as FAILED so that subsequent retries are permitted.
        """
        with self.transaction(conn) as tx:
            with tx.cursor() as cur:
                cur.execute(
                    """
                    UPDATE processed_events 
                    SET status = 'FAILED', error_message = %s, updated_at = NOW() 
                    WHERE event_id = %s AND payment_id = %s;
                    """,
                    (error_msg[:500] if error_msg else "Processing failed", event_id, payment_id)
                )

    def check_and_register_event(
        self,
        event_id: str,
        payment_id: str,
        payload_str: str,
        conn=None
    ) -> bool:
        """
        Legacy/Durable Idempotency Guard:
        Stores canonical payload hash and event hash.
        Returns True if this is the first delivery (inserted).
        Returns False if replayed/duplicate event (rejected).
        """
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        event_hash = hashlib.sha256(f"{event_id}:{payload_str}".encode("utf-8")).hexdigest()

        with self.transaction(conn) as tx:
            with tx.cursor() as cur:
                # Attempt to insert; ON CONFLICT DO NOTHING handles duplicate event_hash or (event_id, payment_id)
                cur.execute(
                    """
                    INSERT INTO processed_events (
                        event_hash, event_id, payment_id, payload_hash, first_processed_at, status
                    ) VALUES (%s, %s, %s, %s, NOW(), 'PROCESSED')
                    ON CONFLICT (event_id, payment_id) DO NOTHING
                    RETURNING event_hash;
                    """,
                    (event_hash, event_id, payment_id, payload_hash)
                )
                inserted = cur.fetchone()
                return inserted is not None

    # =========================================================================
    # Startup Health & Validation
    # =========================================================================

    def validate_database_health(self) -> bool:
        """
        Validates live connectivity to PostgreSQL database.
        """
        with self.transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                row = cur.fetchone()
                return row is not None

    def validate_migration_schema(self) -> Tuple[bool, List[str]]:
        """
        Validates that all required tables and schema migrations exist in PostgreSQL.
        """
        required_tables = [
            "payment_cases",
            "state_transitions",
            "processed_events",
            "audit_blocks",
            "merchant_policies"
        ]
        missing_tables = []
        with self.transaction() as conn:
            with conn.cursor() as cur:
                for table in required_tables:
                    cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = %s
                        );
                        """,
                        (table,)
                    )
                    exists = cur.fetchone()[0]
                    if not exists:
                        missing_tables.append(table)
        return len(missing_tables) == 0, missing_tables

    # =========================================================================
    # 3. Cryptographic Audit Ledger Blocks
    # =========================================================================

    def record_audit_block(
        self,
        telemetry: TransactionTelemetry,
        policy_decision: PolicyDecision,
        action_executed: str,
        resulting_state: str,
        ai_reasoning: Optional[AIReasonerOutput] = None,
        correlation_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        policy_version: Optional[str] = None,
        model_name: Optional[str] = None,
        prompt_version: Optional[str] = None,
        before_state: Optional[str] = None,
        after_state: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        conn=None
    ) -> AuditBlock:
        """
        Records an immutable audit block in PostgreSQL.
        Uses PostgreSQL table/row locking to ensure concurrency-safe sequential block indexing
        and strict cryptographic hash-chaining without race conditions.
        """
        with self.transaction(conn) as tx:
            with tx.cursor(cursor_factory=RealDictCursor) as cur:
                # Explicit advisory transaction lock to serialize audit block additions
                # 0x52415A50 is hex for 'RAZP' (1380014672)
                cur.execute("SELECT pg_advisory_xact_lock(1380014672);")

                # Fetch the latest audit block
                cur.execute(
                    "SELECT block_index, current_hash FROM audit_blocks ORDER BY block_index DESC LIMIT 1;"
                )
                last_block = cur.fetchone()

                if last_block:
                    index = last_block["block_index"] + 1
                    previous_hash = last_block["current_hash"]
                else:
                    index = 0
                    previous_hash = AuditLedger.GENESIS_HASH

                timestamp = policy_decision.timestamp.isoformat()

                # Calculate telemetry hash using model_dump(mode='json')
                telem_dump = telemetry.model_dump(mode="json")
                telem_encoded = json.dumps(telem_dump, sort_keys=True, default=str).encode("utf-8")
                telem_hash = hashlib.sha256(telem_encoded).hexdigest()

                ai_dump = ai_reasoning.model_dump(mode="json") if ai_reasoning else None
                pol_dump = policy_decision.model_dump(mode="json")

                # Use canonical hashing logic matching AuditLedger._calculate_hash
                payload = {
                    "index": index,
                    "timestamp": timestamp,
                    "payment_id": telemetry.payment_id,
                    "telemetry_hash": telem_hash,
                    "ai_reasoning": ai_dump,
                    "policy_decision": pol_dump,
                    "action_executed": action_executed,
                    "resulting_state": resulting_state,
                    "previous_hash": previous_hash
                }
                encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
                current_hash = hashlib.sha256(encoded).hexdigest()

                cur.execute(
                    """
                    INSERT INTO audit_blocks (
                        block_index, payment_id, telemetry_hash, ai_reasoning,
                        policy_decision, action_executed, resulting_state,
                        previous_hash, current_hash, block_timestamp, block_timestamp_dt,
                        correlation_id, actor_id, policy_version, model_name,
                        prompt_version, before_state, after_state, idempotency_key, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::timestamptz,
                        %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                    )
                    RETURNING *;
                    """,
                    (
                        index,
                        telemetry.payment_id,
                        telem_hash,
                        Json(ai_dump) if ai_dump is not None else None,
                        Json(pol_dump),
                        action_executed,
                        resulting_state,
                        previous_hash,
                        current_hash,
                        timestamp,
                        timestamp,
                        correlation_id,
                        actor_id,
                        policy_version,
                        model_name,
                        prompt_version,
                        before_state,
                        after_state,
                        idempotency_key
                    )
                )

                return AuditBlock(
                    index=index,
                    timestamp=timestamp,
                    payment_id=telemetry.payment_id,
                    telemetry_hash=telem_hash,
                    ai_reasoning=ai_dump,
                    policy_decision=pol_dump,
                    action_executed=action_executed,
                    resulting_state=resulting_state,
                    previous_hash=previous_hash,
                    current_hash=current_hash,
                    correlation_id=correlation_id,
                    actor_id=actor_id,
                    policy_version=policy_version,
                    model_name=model_name,
                    prompt_version=prompt_version,
                    before_state=before_state,
                    after_state=after_state,
                    idempotency_key=idempotency_key
                )

    def get_ledger_blocks(self, conn=None) -> List[AuditBlock]:
        """
        Retrieves all persisted audit ledger blocks in sequential order.
        """
        with self.transaction(conn) as tx:
            with tx.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM audit_blocks ORDER BY block_index ASC;")
                rows = cur.fetchall()
                blocks = []
                for r in rows:
                    blocks.append(AuditBlock(
                        index=r["block_index"],
                        timestamp=str(r["block_timestamp"]),
                        payment_id=r["payment_id"],
                        telemetry_hash=r["telemetry_hash"],
                        ai_reasoning=r["ai_reasoning"],
                        policy_decision=r["policy_decision"],
                        action_executed=r["action_executed"],
                        resulting_state=r["resulting_state"],
                        previous_hash=r["previous_hash"],
                        current_hash=r["current_hash"],
                        correlation_id=r.get("correlation_id"),
                        actor_id=r.get("actor_id"),
                        policy_version=r.get("policy_version"),
                        model_name=r.get("model_name"),
                        prompt_version=r.get("prompt_version"),
                        before_state=r.get("before_state"),
                        after_state=r.get("after_state"),
                        idempotency_key=r.get("idempotency_key"),
                        block_timestamp_dt=r.get("block_timestamp_dt")
                    ))
                return blocks

    def verify_persisted_ledger_integrity(self, conn=None) -> Tuple[bool, Optional[str]]:
        """
        Cryptographically validates the entire persisted audit block chain from PostgreSQL.
        """
        blocks = self.get_ledger_blocks(conn=conn)
        for i, block in enumerate(blocks):
            expected_prev = AuditLedger.GENESIS_HASH if i == 0 else blocks[i - 1].current_hash
            if block.previous_hash != expected_prev:
                return False, f"Broken link at block {i}: previous_hash mismatch (expected {expected_prev}, got {block.previous_hash})"

            payload = {
                "index": block.index,
                "timestamp": block.timestamp,
                "payment_id": block.payment_id,
                "telemetry_hash": block.telemetry_hash,
                "ai_reasoning": block.ai_reasoning,
                "policy_decision": block.policy_decision,
                "action_executed": block.action_executed,
                "resulting_state": block.resulting_state,
                "previous_hash": block.previous_hash
            }
            encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            recomputed = hashlib.sha256(encoded).hexdigest()

            if block.current_hash != recomputed:
                return False, f"Tampered block at index {i}: current_hash mismatch"

        return True, None

    # =========================================================================
    # 4. Merchant Policy Persistence
    # =========================================================================

    def get_active_merchant_policy(
        self,
        merchant_id: str = "rzp_merchant_prod",
        conn=None
    ) -> MerchantPolicy:
        """
        Loads the currently active MerchantPolicy for a given merchant_id.
        """
        with self.transaction(conn) as tx:
            with tx.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM merchant_policies
                    WHERE merchant_id = %s AND is_active = TRUE
                    LIMIT 1;
                    """,
                    (merchant_id,)
                )
                row = cur.fetchone()
                if not row:
                    # Fallback default if not seeded
                    return MerchantPolicy(merchant_id=merchant_id)

                def parse_time(val):
                    if isinstance(val, time):
                        return val
                    if isinstance(val, str):
                        parts = val.split(":")
                        return time(int(parts[0]), int(parts[1]))
                    return time(21, 0)

                return MerchantPolicy(
                    merchant_id=row["merchant_id"],
                    quiet_hours_start=parse_time(row["quiet_hours_start"]),
                    quiet_hours_end=parse_time(row["quiet_hours_end"]),
                    max_contact_attempts=int(row["max_contact_attempts"]),
                    max_ptp_extension_days=int(row["max_ptp_extension_days"]),
                    allow_discounts=bool(row["allow_discounts"]),
                    circuit_breaker_bank_failure_rate_threshold=float(row["circuit_breaker_threshold"]),
                    cost_per_sms=float(row["cost_per_sms"]),
                    cost_per_whatsapp=float(row["cost_per_whatsapp"]),
                    cost_per_llm_inference=float(row["cost_per_llm_inference"]),
                    cost_per_failed_bank_retry=float(row["cost_per_failed_bank_retry"]),
                    chargeback_dispute_fee=float(row["chargeback_dispute_fee"])
                )

    def set_active_merchant_policy(
        self,
        policy: MerchantPolicy,
        conn=None
    ) -> int:
        """
        Inserts a new merchant policy row and activates it, deactivating any prior active policy.
        Enforces partial unique constraint on (merchant_id) WHERE is_active = TRUE.
        """
        with self.transaction(conn) as tx:
            with tx.cursor(cursor_factory=RealDictCursor) as cur:
                # Deactivate previous active policies for this merchant
                cur.execute(
                    "UPDATE merchant_policies SET is_active = FALSE, updated_at = NOW() WHERE merchant_id = %s AND is_active = TRUE;",
                    (policy.merchant_id,)
                )

                cur.execute(
                    """
                    INSERT INTO merchant_policies (
                        merchant_id, quiet_hours_start, quiet_hours_end,
                        max_contact_attempts, max_ptp_extension_days,
                        allow_discounts, circuit_breaker_threshold,
                        cost_per_sms, cost_per_whatsapp, cost_per_llm_inference,
                        cost_per_failed_bank_retry, chargeback_dispute_fee,
                        is_active, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW()
                    )
                    RETURNING id;
                    """,
                    (
                        policy.merchant_id,
                        policy.quiet_hours_start.strftime("%H:%M:%S"),
                        policy.quiet_hours_end.strftime("%H:%M:%S"),
                        policy.max_contact_attempts,
                        policy.max_ptp_extension_days,
                        policy.allow_discounts,
                        policy.circuit_breaker_bank_failure_rate_threshold,
                        policy.cost_per_sms,
                        policy.cost_per_whatsapp,
                        policy.cost_per_llm_inference,
                        policy.cost_per_failed_bank_retry,
                        policy.chargeback_dispute_fee
                    )
                )
                new_id = cur.fetchone()["id"]
                return new_id
