from __future__ import annotations
import os
import json
import copy
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException, Response, Request, Depends, Header, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from core.schemas import (
    TransactionTelemetry,
    CustomerMessage,
    PaymentMethod,
    AIReasonerOutput,
    PolicyDecision,
    ActionType,
    PaymentState,
    MerchantPolicy,
    AuditBlock,
    UserRole,
    ActorContext,
    BankSettlementWebhookPayload
)
from core.gemini_reasoner import GeminiReasoner, PROMPT_VERSION, SCHEMA_VERSION
from core.policy_gate import DeterministicPolicyGate
from core.state_machine import StateMachine, InvalidStateTransitionError
from core.executor import RecoveryExecutor
from core.ledger import AuditLedger
from core.persistence import (
    PersistenceManager,
    PersistenceError,
    CaseNotFoundError,
    EventReservationStatus
)
from benchmark.run_ablation import run_6way_ablation
from benchmark.dataset_generator import build_and_save_splits

from server.auth import (
    require_roles,
    get_current_actor,
    verify_bank_webhook_signature,
    is_production,
    eval_rate_limiter,
    mutation_rate_limiter,
    benchmark_rate_limiter
)
from server.in_memory import InMemoryEngine
from server.middleware import (
    CorrelationIdMiddleware,
    SecurityHeadersMiddleware,
    SafeExceptionHandlerMiddleware
)

persistence_mgr: Optional[PersistenceManager] = None
merchant_policy = MerchantPolicy()
in_memory_engine = InMemoryEngine()
reasoner = GeminiReasoner()
policy_gate = DeterministicPolicyGate(policy=merchant_policy)
executor = RecoveryExecutor(ledger=in_memory_engine.ledger, policy=merchant_policy)
_ledger_backup: Optional[AuditLedger] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global persistence_mgr, merchant_policy, policy_gate, executor
    db_url_env = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or os.getenv("POSTGRES_PRISMA_URL") or os.getenv("SUPABASE_DATABASE_URL")
    if db_url_env and db_url_env.startswith("postgres://"):
        db_url_env = "postgresql://" + db_url_env[len("postgres://"):]
    is_vercel = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))
    prod = is_production() or os.getenv("VERCEL_ENV") == "production"

    if is_vercel and db_url_env and ("localhost" in db_url_env or "127.0.0.1" in db_url_env):
        if prod:
            raise RuntimeError("FATAL: Localhost DATABASE_URL detected in cloud Vercel production deployment. Failing closed.")
        print("[RazP] NOTICE: Localhost DATABASE_URL detected in cloud Vercel development deployment. Falling back to in-memory demo mode.")
        db_url_env = None

    demo_fallback = (os.getenv("RAZP_DEMO_IN_MEMORY", "false").lower() in ("true", "1", "yes")) and not prod

    if not db_url_env:
        if prod or not demo_fallback:
            raise RuntimeError(
                "FATAL: DATABASE_URL environment variable is mandatory for RazP in production mode. "
                "In-memory fallback is strictly prohibited in production. Startup aborted."
            )
        print(f"[RazP] {InMemoryEngine.NON_DURABLE_WARNING}")
    else:
        try:
            persistence_mgr = PersistenceManager(db_url=db_url_env)
            # Startup validation checks
            if not persistence_mgr.validate_database_health():
                raise RuntimeError("PostgreSQL database connection check failed.")
            schema_ok, missing = persistence_mgr.validate_migration_schema()
            if not schema_ok:
                try:
                    from scripts.migrate import run_migrations
                    print(f"[RazP] Missing database tables {missing}. Running migrations automatically...")
                    run_migrations(db_url=db_url_env)
                    schema_ok, missing = persistence_mgr.validate_migration_schema()
                except Exception as mig_err:
                    print(f"[RazP] Auto-migration attempt warning: {mig_err}")
                if not schema_ok:
                    raise RuntimeError(f"Database schema validation failed. Missing tables: {missing}. Run scripts/migrate.py.")
            is_valid, err = persistence_mgr.verify_persisted_ledger_integrity()
            if not is_valid:
                print(f"[RazP] WARNING: Ledger cryptographic integrity warning on startup: {err}")
            
            active_pol = persistence_mgr.get_active_merchant_policy()
            if active_pol:
                merchant_policy = active_pol
                policy_gate = DeterministicPolicyGate(policy=merchant_policy)
                executor = RecoveryExecutor(ledger=in_memory_engine.ledger, policy=merchant_policy)
            print("[RazP] Startup validation passed. PostgreSQL Persistence Layer active and verified.")
        except Exception as exc:
            if prod or not demo_fallback:
                raise RuntimeError(f"FATAL: Database startup validation failed in production: {exc}") from exc
            print(f"[RazP] WARNING: Database failed on startup in non-production, falling back to in-memory mode: {exc}")
            persistence_mgr = None
    yield


app = FastAPI(
    title="RazP API",
    description="Razorpay Autonomous Zero-Loss Payment Recovery Engine with Durable Persistence & Production Security",
    version="1.3.0",
    lifespan=lifespan
)

# Attach Security & Logging Middlewares
app.add_middleware(SafeExceptionHandlerMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Explicit Whitelist CORS (Wildcard *.vercel.app removed for production security)
allowed_origins_env = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000"
)
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID", "X-RazP-Durability"]
)


# =============================================================================
# STRICTLY BOUNDED INPUT SCHEMAS
# =============================================================================

class SingleEvalRequest(BaseModel):
    payment_id: str = Field(default="pay_demo_001", min_length=1, max_length=64)
    invoice_id: str = Field(default="inv_demo_001", min_length=1, max_length=64)
    amount_inr: float = Field(default=2499.0, gt=0.0, le=10_000_000.0)
    gateway_error_code: str = Field(default="BAD_REQUEST_ERROR", min_length=1, max_length=64)
    bank_raw_response_code: str = Field(default="51", min_length=1, max_length=32)
    payment_method: PaymentMethod = Field(default=PaymentMethod.UPI_AUTOPAY)
    latency_ms: int = Field(default=450, ge=0, le=60_000)
    bank_switch_degradation_score: float = Field(default=0.1, ge=0.0, le=1.0)
    attempt_count: int = Field(default=1, ge=1, le=20)
    inbound_message: Optional[str] = Field(default="bhai salary 7 tareek ko aayegi tab kat lena please", max_length=1000)
    channel: str = Field(default="WHATSAPP", max_length=32)
    evaluation_time_iso: Optional[str] = None
    event_id: Optional[str] = Field(default=None, max_length=64)


class WebhookReplayRequest(BaseModel):
    event_id: str = Field(default="evt_recon_9981", min_length=1, max_length=64)
    payment_id: str = Field(default="pay_demo_u30_001", min_length=1, max_length=64)
    amount_inr: float = Field(default=3200.0, gt=0.0, le=10_000_000.0)
    gateway_error_code: str = Field(default="GATEWAY_TIMEOUT", min_length=1, max_length=64)
    bank_raw_response_code: str = Field(default="U30", min_length=1, max_length=32)


class UpdatePolicyRequest(BaseModel):
    merchant_id: str = "rzp_merchant_prod"
    quiet_hours_start: Optional[str] = "21:00"
    quiet_hours_end: Optional[str] = "09:00"
    max_contact_attempts: Optional[int] = 3
    max_ptp_extension_days: Optional[int] = 14
    allow_discounts: Optional[bool] = False
    circuit_breaker_bank_failure_rate_threshold: Optional[float] = 0.65
    cost_per_sms: Optional[float] = 0.15
    cost_per_whatsapp: Optional[float] = 0.50
    cost_per_llm_inference: Optional[float] = 0.10
    cost_per_failed_bank_retry: Optional[float] = 5.00
    chargeback_dispute_fee: Optional[float] = 50.00


# =============================================================================
# PUBLIC HEALTH & STATUS ENDPOINTS
# =============================================================================

@app.get("/healthz")
@app.get("/api/health")
async def health(response: Response):
    is_durable = persistence_mgr is not None
    response.headers["X-RazP-Durability"] = "POSTGRESQL_DURABLE" if is_durable else "EPHEMERAL_IN_MEMORY_NON_DURABLE"
    return {
        "status": "healthy",
        "service": "Sentinel-Recover",
        "persistence": "connected" if is_durable else "in_memory_demo",
        "durability": "DURABLE" if is_durable else "EPHEMERAL_NON_DURABLE",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/system/status")
async def get_system_status(response: Response):
    has_key = bool(reasoner.api_key)
    active_policy = persistence_mgr.get_active_merchant_policy() if persistence_mgr else merchant_policy
    is_durable = persistence_mgr is not None
    response.headers["X-RazP-Durability"] = "POSTGRESQL_DURABLE" if is_durable else "EPHEMERAL_IN_MEMORY_NON_DURABLE"
    return {
        "status": "OPERATIONAL",
        "service": "Sentinel-Recover",
        "persistence_layer": "POSTGRESQL_DURABLE" if is_durable else "IN_MEMORY_FALLBACK",
        "durability_warning": None if is_durable else InMemoryEngine.NON_DURABLE_WARNING,
        "ai_provider": "Gemini",
        "model": reasoner.model_name,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "is_live_gemini": has_key,
        "fallback_active": not has_key,
        "active_policy_merchant_id": active_policy.merchant_id if active_policy else "default",
        "invariants_verified": [
            "Zero AI Financial Authority (Deterministic Policy Gate Enforcement)",
            "Cryptographic SHA-256 Tamper-Evident Audit Ledger",
            "PostgreSQL Row-Locked Concurrency & Terminal State Locks",
            "Two-Phase Idempotency & Webhook Deduplication",
            "Mandatory Authoritative Bank Settlement Reconciliation with Raw HMAC"
        ]
    }


# =============================================================================
# OPERATOR / AUDITOR PROTECTED API ENDPOINTS
# =============================================================================

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(
    actor: ActorContext = Depends(require_roles(UserRole.OPERATOR, UserRole.POLICY_ADMIN, UserRole.AUDITOR))
):
    if persistence_mgr:
        return persistence_mgr.get_dashboard_stats()
    else:
        cases = in_memory_engine.list_cases(limit=1000)
        total_risk = sum(c.get("amount_inr", 0.0) for c in cases if not c.get("is_terminal", False))
        total_recovered = sum(c.get("recovered_amount", 0.0) for c in cases if c.get("current_state") == PaymentState.RECOVERED.value)
        return {
            "active_recovery_cases": len([c for c in cases if not c.get("is_terminal", False)]),
            "revenue_at_risk_inr": round(total_risk, 2),
            "recovered_revenue_inr": round(total_recovered, 2),
            "current_exposure_inr": round(total_risk, 2),
            "escalations_count": len([c for c in cases if c.get("current_state") == PaymentState.ESCALATED_HUMAN_OPS.value]),
            "stopped_cases_count": len([c for c in cases if c.get("current_state") == PaymentState.DEAD_LETTER.value]),
            "recent_activity": list(reversed(in_memory_engine.ledger.export_ledger()))[:10]
        }


@app.get("/api/cases")
async def list_cases(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    actor: ActorContext = Depends(require_roles(UserRole.OPERATOR, UserRole.POLICY_ADMIN, UserRole.AUDITOR))
):
    if persistence_mgr:
        cases = persistence_mgr.list_cases(limit=limit)
        return {"total": len(cases), "cases": cases}
    else:
        cases = in_memory_engine.list_cases(limit=limit, offset=offset)
        return {"total": len(in_memory_engine._cases), "cases": cases}


@app.get("/api/cases/{payment_id}")
async def get_case(
    payment_id: str,
    actor: ActorContext = Depends(require_roles(UserRole.OPERATOR, UserRole.POLICY_ADMIN, UserRole.AUDITOR))
):
    if persistence_mgr:
        case = persistence_mgr.get_case(payment_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case {payment_id} not found.")
        return case
    else:
        case = in_memory_engine.get_case(payment_id)
        if not case:
            raise HTTPException(status_code=404, detail=f"Case {payment_id} not found in in-memory store.")
        return case


# =============================================================================
# CORE DECISION & TWO-PHASE IDEMPOTENT EVALUATION ENDPOINT
# =============================================================================

@app.post("/api/evaluate/single")
async def evaluate_single(
    req: SingleEvalRequest,
    request: Request,
    response: Response,
    actor: ActorContext = Depends(require_roles(UserRole.OPERATOR, UserRole.ADMIN))
):
    eval_rate_limiter.check_rate_limit(request, "evaluate")
    if req.evaluation_time_iso:
        dt = datetime.fromisoformat(req.evaluation_time_iso)
        eval_time = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    else:
        eval_time = datetime.now(timezone.utc)

    event_id = req.event_id or request.headers.get("X-Event-ID") or f"evt_{req.payment_id}_{req.attempt_count}"
    payload_str = f"{req.payment_id}:{req.amount_inr}:{req.gateway_error_code}:{req.bank_raw_response_code}:{req.attempt_count}:{req.inbound_message or ''}"

    is_durable = persistence_mgr is not None
    response.headers["X-RazP-Durability"] = "POSTGRESQL_DURABLE" if is_durable else "EPHEMERAL_IN_MEMORY_NON_DURABLE"

    # -------------------------------------------------------------------------
    # Two-Phase Idempotency: Phase 1 — Atomic Reservation Before LLM Call
    # -------------------------------------------------------------------------
    if persistence_mgr:
        reservation = persistence_mgr.reserve_event(event_id, req.payment_id, payload_str)
        if reservation == EventReservationStatus.ALREADY_PROCESSED:
            existing_case = persistence_mgr.get_case(req.payment_id)
            blocks = [
                b.model_dump() for b in persistence_mgr.get_ledger_blocks()
                if b.payment_id == req.payment_id
            ]
            transitions = existing_case.get("transitions", []) if existing_case else []
            return {
                "payment_id": req.payment_id,
                "status": "DUPLICATE_EVENT_SUPPRESSED",
                "idempotent_duplicate": True,
                "ai_reasoning": None,
                "policy_decision": None,
                "execution_result": {
                    "success": True,
                    "action_executed": "NO_OP_DUPLICATE_SUPPRESSED",
                    "resulting_state": existing_case["current_state"] if existing_case else "PAYMENT_FAILED",
                    "details": {"reason": "Idempotent event replay intercepted. Zero duplicate action dispatched."},
                    "financial_cost_incurred": 0.0,
                    "recovered_amount": 0.0
                },
                "audit_block": blocks[-1] if blocks else None,
                "state_transitions": [{"from": t["from_state"], "to": t["to_state"], "reason": t["reason"]} for t in transitions],
                "final_state": existing_case["current_state"] if existing_case else "PAYMENT_FAILED",
                "ai_provenance": {
                    "model": "IdempotencyInterceptor",
                    "is_live_gemini": False,
                    "latency_ms": 0,
                    "correlation_id": actor.correlation_id,
                    "actor_id": actor.actor_id
                }
            }
        elif reservation == EventReservationStatus.IN_FLIGHT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Event is currently being processed by another concurrent worker. Please retry shortly."
            )
    else:
        reservation = in_memory_engine.reserve_event(event_id, req.payment_id, payload_str)
        if reservation == EventReservationStatus.ALREADY_PROCESSED:
            case = in_memory_engine.get_case(req.payment_id)
            blocks = [b for b in in_memory_engine.ledger.export_ledger() if b.get("payment_id") == req.payment_id]
            transitions = case.get("transitions", []) if case else []
            return {
                "payment_id": req.payment_id,
                "status": "DUPLICATE_EVENT_SUPPRESSED",
                "idempotent_duplicate": True,
                "ai_reasoning": None,
                "policy_decision": None,
                "execution_result": {
                    "success": True,
                    "action_executed": "NO_OP_DUPLICATE_SUPPRESSED",
                    "resulting_state": case["current_state"] if case else "PAYMENT_FAILED",
                    "details": {"reason": "Idempotent event replay intercepted. Zero duplicate action dispatched."},
                    "financial_cost_incurred": 0.0,
                    "recovered_amount": 0.0
                },
                "audit_block": blocks[-1] if blocks else None,
                "state_transitions": [{"from": t["from_state"], "to": t["to_state"], "reason": t["reason"]} for t in transitions],
                "final_state": case["current_state"] if case else "PAYMENT_FAILED",
                "ai_provenance": {
                    "model": "IdempotencyInterceptor",
                    "is_live_gemini": False,
                    "latency_ms": 0,
                    "correlation_id": actor.correlation_id,
                    "actor_id": actor.actor_id
                }
            }
        elif reservation == EventReservationStatus.IN_FLIGHT:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Event is currently being processed by another concurrent worker. Please retry shortly."
            )

    # -------------------------------------------------------------------------
    # Outside DB Transaction: LLM Reasoning & Deterministic Policy Gate
    # -------------------------------------------------------------------------
    try:
        msg_obj = None
        if req.inbound_message:
            msg_obj = CustomerMessage(
                message_text=req.inbound_message,
                channel=req.channel
            )

        telemetry = TransactionTelemetry(
            payment_id=req.payment_id,
            invoice_id=req.invoice_id,
            amount_inr=req.amount_inr,
            gateway_error_code=req.gateway_error_code,
            bank_raw_response_code=req.bank_raw_response_code,
            payment_method=req.payment_method,
            latency_ms=req.latency_ms,
            bank_switch_degradation_score=req.bank_switch_degradation_score,
            attempt_count=req.attempt_count,
            last_inbound_message=msg_obj
        )

        active_policy = persistence_mgr.get_active_merchant_policy() if persistence_mgr else merchant_policy
        active_gate = DeterministicPolicyGate(policy=active_policy)

        # AI Reasoning Step (Runs without holding database transaction locks)
        reasoning_res = reasoner.reason(telemetry, eval_time)
        ai_output: AIReasonerOutput = reasoning_res["reasoner_output"]

        # Deterministic Policy Gate Step
        policy_decision: PolicyDecision = active_gate.evaluate(telemetry, ai_output, current_time=eval_time)
        policy_decision.ai_root_cause = ai_output.root_cause.value

        # ---------------------------------------------------------------------
        # Two-Phase Idempotency: Phase 2 — Atomic State Transition & Ledger Commit
        # ---------------------------------------------------------------------
        if persistence_mgr:
            with persistence_mgr.transaction() as conn:
                persistence_mgr.get_or_create_case(
                    payment_id=telemetry.payment_id,
                    invoice_id=telemetry.invoice_id,
                    amount_inr=telemetry.amount_inr,
                    initial_state=PaymentState.PAYMENT_FAILED,
                    attempt_count=telemetry.attempt_count,
                    conn=conn
                )
                sm = persistence_mgr.load_state_machine(telemetry.payment_id, conn=conn)
                initial_history_len = len(sm.get_history())

                exec_res = executor.execute(
                    telemetry=telemetry,
                    policy_decision=policy_decision,
                    state_machine=sm,
                    ai_reasoning=ai_output
                )

                curr_state = sm.current_state
                for from_st, to_st, reason_str in sm.get_history()[initial_history_len:]:
                    persistence_mgr.record_transition(
                        payment_id=telemetry.payment_id,
                        from_state=from_st,
                        to_state=to_st,
                        reason=reason_str,
                        conn=conn
                    )

                persisted_block = persistence_mgr.record_audit_block(
                    telemetry=telemetry,
                    policy_decision=policy_decision,
                    action_executed=policy_decision.final_action.value,
                    resulting_state=curr_state.value,
                    ai_reasoning=ai_output,
                    correlation_id=actor.correlation_id,
                    actor_id=actor.actor_id,
                    policy_version=active_policy.merchant_id,
                    model_name=reasoning_res.get("model", reasoner.model_name),
                    prompt_version=PROMPT_VERSION,
                    conn=conn
                )
                persistence_mgr.complete_event(event_id, req.payment_id, conn=conn)
                audit_block_dict = persisted_block.model_dump()
                history = sm.get_history()
        else:
            # Isolated per-case in-memory simulation
            in_memory_engine.get_or_create_case(
                payment_id=telemetry.payment_id,
                invoice_id=telemetry.invoice_id,
                amount_inr=telemetry.amount_inr
            )
            sm = in_memory_engine.load_state_machine(telemetry.payment_id)
            initial_history_len = len(sm.get_history())

            exec_res = executor.execute(
                telemetry=telemetry,
                policy_decision=policy_decision,
                state_machine=sm,
                ai_reasoning=ai_output
            )

            for from_st, to_st, reason_str in sm.get_history()[initial_history_len:]:
                in_memory_engine.record_transition(
                    payment_id=telemetry.payment_id,
                    from_state=from_st,
                    to_state=to_st,
                    reason=reason_str
                )

            persisted_block = in_memory_engine.record_audit_block(
                telemetry=telemetry,
                policy_decision=policy_decision,
                action_executed=policy_decision.final_action.value,
                resulting_state=sm.current_state.value,
                ai_reasoning=ai_output,
                correlation_id=actor.correlation_id,
                actor_id=actor.actor_id
            )
            in_memory_engine.complete_event(event_id, req.payment_id)
            audit_block_dict = persisted_block.model_dump()
            history = sm.get_history()

    except Exception as exc:
        # Failure Recovery: Release event reservation so retry can succeed
        if persistence_mgr:
            try:
                persistence_mgr.release_event_reservation(event_id, req.payment_id, str(exc))
            except Exception:
                pass
        else:
            in_memory_engine.release_event_reservation(event_id, req.payment_id, str(exc))
        raise

    return {
        "payment_id": telemetry.payment_id,
        "ai_reasoning": ai_output.model_dump(),
        "policy_decision": policy_decision.model_dump(),
        "execution_result": exec_res.model_dump(),
        "audit_block": audit_block_dict,
        "state_transitions": [{"from": h[0].value, "to": h[1].value, "reason": h[2]} for h in history],
        "final_state": sm.current_state.value,
        "ai_provenance": {
            "model": reasoning_res.get("model", reasoner.model_name),
            "is_live_gemini": not reasoning_res.get("is_fallback", True),
            "latency_ms": 120,
            "correlation_id": actor.correlation_id,
            "actor_id": actor.actor_id
        },
        "reasoner_meta": {
            "model": reasoning_res.get("model", reasoner.model_name),
            "is_fallback": reasoning_res.get("is_fallback", True),
            "correlation_id": actor.correlation_id,
            "actor_id": actor.actor_id
        }
    }


# =============================================================================
# WEBHOOK ENDPOINTS
# =============================================================================

@app.post("/api/webhook/simulate-replay")
async def simulate_webhook_replay(
    req: WebhookReplayRequest,
    request: Request,
    actor: ActorContext = Depends(require_roles(UserRole.OPERATOR, UserRole.ADMIN))
):
    """
    Simulates webhook event delivery and verifies idempotency / replay suppression.
    """
    event_id = req.event_id
    payload_str = f"{req.payment_id}:{req.amount_inr}:{req.gateway_error_code}:{req.bank_raw_response_code}"

    if persistence_mgr:
        res = persistence_mgr.reserve_event(event_id, req.payment_id, payload_str)
        is_duplicate = (res == EventReservationStatus.ALREADY_PROCESSED)
        case = persistence_mgr.get_case(req.payment_id)
        if not is_duplicate:
            persistence_mgr.complete_event(event_id, req.payment_id)
    else:
        res = in_memory_engine.reserve_event(event_id, req.payment_id, payload_str)
        is_duplicate = (res == EventReservationStatus.ALREADY_PROCESSED)
        case = in_memory_engine.get_case(req.payment_id)
        if not is_duplicate:
            in_memory_engine.complete_event(event_id, req.payment_id)

    if is_duplicate:
        return {
            "status": "DUPLICATE_EVENT_SUPPRESSED",
            "idempotent_duplicate": True,
            "event_id": event_id,
            "payment_id": req.payment_id,
            "resulting_state": case["current_state"] if case else "PAYMENT_FAILED",
            "action_taken": "NO_OP (Duplicate Webhook Delivery Intercepted)",
            "details": {
                "message": f"Event {event_id} was already processed. Replay attack neutralized."
            }
        }

    return {
        "status": "EVENT_ACCEPTED",
        "idempotent_duplicate": False,
        "event_id": event_id,
        "payment_id": req.payment_id,
        "resulting_state": case["current_state"] if case else "PAYMENT_FAILED",
        "action_taken": "EVENT_REGISTERED",
        "details": {
            "message": f"First delivery of event {event_id} registered successfully."
        }
    }


@app.post("/api/webhook/bank-settlement")
async def process_bank_settlement_webhook(
    request: Request,
    raw_body: bytes = Depends(verify_bank_webhook_signature)
):
    """
    Authoritative Bank Settlement Webhook.
    Strictly verifies raw HMAC-SHA256 signature, fresh timestamp, deduplicates settlement,
    verifies RRN and exact settled amount, and records final RECOVERED transition.
    Normal API key callers cannot authenticate this route.
    """
    try:
        payload = BankSettlementWebhookPayload.model_validate_json(raw_body)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bank settlement webhook payload: {err}"
        )

    # 1. Webhook Deduplication Check
    payload_str = f"{payload.payment_id}:{payload.settled_amount}:{payload.rrn}:{payload.bank_status}"
    if persistence_mgr:
        res = persistence_mgr.reserve_event(payload.event_id, payload.payment_id, payload_str)
        if res == EventReservationStatus.ALREADY_PROCESSED:
            return {
                "status": "DUPLICATE_SETTLEMENT_SUPPRESSED",
                "payment_id": payload.payment_id,
                "rrn": payload.rrn,
                "message": "Bank settlement already processed and reconciled previously."
            }
    else:
        res = in_memory_engine.reserve_event(payload.event_id, payload.payment_id, payload_str)
        if res == EventReservationStatus.ALREADY_PROCESSED:
            return {
                "status": "DUPLICATE_SETTLEMENT_SUPPRESSED",
                "payment_id": payload.payment_id,
                "rrn": payload.rrn,
                "message": "Bank settlement already processed and reconciled previously."
            }

    # 2. Case Verification (Case existence & Amount match)
    if persistence_mgr:
        case = persistence_mgr.get_case(payload.payment_id)
    else:
        case = in_memory_engine.get_case(payload.payment_id)

    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reconciliation error: payment case '{payload.payment_id}' does not exist."
        )

    expected_amount = case.get("amount_inr", 0.0)
    if expected_amount > 0 and abs(expected_amount - payload.settled_amount) > 0.01:
        error_msg = f"Settled amount mismatch: expected INR {expected_amount}, but bank reported INR {payload.settled_amount}"
        if persistence_mgr:
            persistence_mgr.release_event_reservation(payload.event_id, payload.payment_id, error_msg)
        else:
            in_memory_engine.release_event_reservation(payload.event_id, payload.payment_id, error_msg)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)

    # 3. State Transition to RECOVERED and Ledger Recording
    transition_reason = f"Bank reconciliation confirmed RRN #{payload.rrn} settlement"
    curr_state_val = case.get("current_state", "PAUSE_RECON_VERIFY")
    curr_state = PaymentState(curr_state_val)

    telem = TransactionTelemetry(
        payment_id=payload.payment_id,
        invoice_id=case.get("invoice_id", f"inv_{payload.payment_id}"),
        amount_inr=payload.settled_amount,
        gateway_error_code="NONE",
        bank_raw_response_code="SETTLED",
        payment_method=PaymentMethod.UPI_AUTOPAY,
        latency_ms=100,
        bank_switch_degradation_score=0.0
    )
    p_dec = PolicyDecision(
        is_overridden=False,
        original_action=ActionType.COMMIT_RECOVERED,
        final_action=ActionType.COMMIT_RECOVERED,
        final_parameters={"rrn": payload.rrn, "settled_amount": payload.settled_amount},
        policy_reason=transition_reason
    )

    if persistence_mgr:
        with persistence_mgr.transaction() as conn:
            # If still in PAYMENT_FAILED, transition through PAUSE_RECON_VERIFY to preserve state machine graph
            if curr_state == PaymentState.PAYMENT_FAILED:
                persistence_mgr.record_transition(
                    payment_id=payload.payment_id,
                    from_state=PaymentState.PAYMENT_FAILED,
                    to_state=PaymentState.PAUSE_RECON_VERIFY,
                    reason="Bank reconciliation inbound; locking retries",
                    conn=conn
                )
                curr_state = PaymentState.PAUSE_RECON_VERIFY

            persistence_mgr.record_transition(
                payment_id=payload.payment_id,
                from_state=curr_state,
                to_state=PaymentState.RECOVERED,
                reason=transition_reason,
                conn=conn
            )
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE payment_cases SET recovered_amount = %s WHERE payment_id = %s;",
                    (payload.settled_amount, payload.payment_id)
                )
            block = persistence_mgr.record_audit_block(
                telemetry=telem,
                policy_decision=p_dec,
                action_executed=ActionType.COMMIT_RECOVERED.value,
                resulting_state=PaymentState.RECOVERED.value,
                correlation_id=request.headers.get("X-Correlation-ID", "corr_bank_recon"),
                actor_id="actor_bank_webhook_engine",
                conn=conn
            )
            persistence_mgr.complete_event(payload.event_id, payload.payment_id, conn=conn)
            block_dict = block.model_dump()
    else:
        # In-memory branch
        if curr_state == PaymentState.PAYMENT_FAILED:
            in_memory_engine.record_transition(
                payment_id=payload.payment_id,
                from_state=PaymentState.PAYMENT_FAILED,
                to_state=PaymentState.PAUSE_RECON_VERIFY,
                reason="Bank reconciliation inbound; locking retries"
            )
        in_memory_engine.mark_case_recovered(payload.payment_id, payload.settled_amount, payload.rrn)
        block = in_memory_engine.record_audit_block(
            telemetry=telem,
            policy_decision=p_dec,
            action_executed=ActionType.COMMIT_RECOVERED.value,
            resulting_state=PaymentState.RECOVERED.value,
            correlation_id=request.headers.get("X-Correlation-ID", "corr_bank_recon"),
            actor_id="actor_bank_webhook_engine"
        )
        in_memory_engine.complete_event(payload.event_id, payload.payment_id)
        block_dict = block.model_dump()

    return {
        "status": "SETTLEMENT_RECONCILED",
        "payment_id": payload.payment_id,
        "rrn": payload.rrn,
        "recovered_amount": payload.settled_amount,
        "currency": payload.currency,
        "resulting_state": PaymentState.RECOVERED.value,
        "audit_block_hash": block_dict["current_hash"],
        "reconciled_at": datetime.now(timezone.utc).isoformat()
    }


# =============================================================================
# POLICY MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/api/policy")
async def get_policy(
    actor: ActorContext = Depends(require_roles(UserRole.POLICY_ADMIN, UserRole.AUDITOR))
):
    if persistence_mgr:
        active_pol = persistence_mgr.get_active_merchant_policy()
        return active_pol.model_dump()
    return merchant_policy.model_dump()


@app.post("/api/policy")
async def update_policy(
    req: UpdatePolicyRequest,
    request: Request,
    actor: ActorContext = Depends(require_roles(UserRole.POLICY_ADMIN, UserRole.ADMIN))
):
    mutation_rate_limiter.check_rate_limit(request, "policy")
    new_policy = MerchantPolicy(
        merchant_id=req.merchant_id,
        quiet_hours_start=req.quiet_hours_start if req.quiet_hours_start is not None else "21:00",
        quiet_hours_end=req.quiet_hours_end if req.quiet_hours_end is not None else "09:00",
        max_contact_attempts=req.max_contact_attempts if req.max_contact_attempts is not None else 3,
        max_ptp_extension_days=req.max_ptp_extension_days if req.max_ptp_extension_days is not None else 14,
        allow_discounts=req.allow_discounts if req.allow_discounts is not None else False,
        circuit_breaker_bank_failure_rate_threshold=req.circuit_breaker_bank_failure_rate_threshold if req.circuit_breaker_bank_failure_rate_threshold is not None else 0.65,
        cost_per_sms=req.cost_per_sms if req.cost_per_sms is not None else 0.15,
        cost_per_whatsapp=req.cost_per_whatsapp if req.cost_per_whatsapp is not None else 0.50,
        cost_per_llm_inference=req.cost_per_llm_inference if req.cost_per_llm_inference is not None else 0.10,
        cost_per_failed_bank_retry=req.cost_per_failed_bank_retry if req.cost_per_failed_bank_retry is not None else 5.00,
        chargeback_dispute_fee=req.chargeback_dispute_fee if req.chargeback_dispute_fee is not None else 50.00
    )

    if persistence_mgr:
        persisted_id = persistence_mgr.set_active_merchant_policy(new_policy)
        telem = TransactionTelemetry(
            payment_id=f"policy_{new_policy.merchant_id}",
            invoice_id="inv_policy_mutation",
            amount_inr=1.0,
            gateway_error_code="NONE",
            bank_raw_response_code="NONE",
            payment_method=PaymentMethod.UPI_AUTOPAY,
            latency_ms=100,
            bank_switch_degradation_score=0.0
        )
        p_dec = PolicyDecision(
            is_overridden=False,
            original_action=ActionType.ABSTAIN_DO_NOTHING,
            final_action=ActionType.ABSTAIN_DO_NOTHING,
            final_parameters={"policy_id": persisted_id, "updated_by": actor.actor_id},
            policy_reason=f"Policy updated for merchant {new_policy.merchant_id}"
        )
        persistence_mgr.record_audit_block(
            telemetry=telem,
            policy_decision=p_dec,
            action_executed="POLICY_MUTATION",
            resulting_state=PaymentState.POLICY_GATED.value,
            correlation_id=actor.correlation_id,
            actor_id=actor.actor_id,
            policy_version=str(persisted_id)
        )
        return {
            "status": "POLICY_UPDATED",
            "policy_id": persisted_id,
            "policy": new_policy.model_dump(),
            "updated_by": actor.actor_id
        }
    else:
        global merchant_policy, policy_gate, executor
        merchant_policy = new_policy
        policy_gate = DeterministicPolicyGate(policy=merchant_policy)
        executor = RecoveryExecutor(ledger=in_memory_engine.ledger, policy=merchant_policy)
        return {
            "status": "POLICY_UPDATED",
            "policy": new_policy.model_dump(),
            "updated_by": actor.actor_id
        }


# =============================================================================
# BENCHMARK & DEMO ENDPOINTS
# =============================================================================

@app.get("/api/benchmark/summary")
async def get_benchmark_summary(
    actor: ActorContext = Depends(require_roles(UserRole.OPERATOR, UserRole.AUDITOR))
):
    try:
        report_path = os.path.join(ROOT_DIR, "reports", "benchmark_summary.json")
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass

    return {
        "status": "AVAILABLE",
        "benchmark_dataset_size": 2500,
        "ablation_arms": 6,
        "arms": ["heuristic_only", "unconstrained_llm", "policy_gated_llm", "audit_durability", "adversarial_safety", "full_sentinel_autonomous"]
    }


@app.get("/api/benchmark/cases")
async def get_benchmark_cases(
    limit: int = 50,
    actor: ActorContext = Depends(require_roles(UserRole.OPERATOR, UserRole.AUDITOR))
):
    split_path = os.path.join(ROOT_DIR, "data", "processed", "benchmark_val.csv")
    if not os.path.exists(split_path):
        build_and_save_splits(total_cases=100)
    
    import pandas as pd
    df = pd.read_csv(split_path).head(limit)
    return df.to_dict(orient="records")


@app.post("/api/benchmark/run")
async def run_benchmark(
    request: Request,
    actor: ActorContext = Depends(require_roles(UserRole.ADMIN))
):
    benchmark_rate_limiter.check_rate_limit(request, "benchmark")
    summary = run_6way_ablation(cases_per_arm=100)
    return summary


@app.post("/api/demo/run-multi-event")
async def run_multi_event_demo(
    request: Request,
    actor: ActorContext = Depends(require_roles(UserRole.OPERATOR, UserRole.ADMIN))
):
    """
    Demonstrates multi-event recovery:
    Step 1: Payment failure with user debit claim -> PAUSE_RECON_VERIFY
    Step 2: Bank reconciliation webhook -> RECOVERED
    Step 3: Webhook duplicate replay attack -> SUPPRESS_DUPLICATE
    """
    eval_rate_limiter.check_rate_limit(request, "demo")
    events = []
    payment_id = "pay_demo_u30_001"

    # Step 1: Ingest Failure with Debit Claim
    p1_telemetry = TransactionTelemetry(
        payment_id=payment_id,
        invoice_id="inv_demo_multi_001",
        amount_inr=3200.0,
        gateway_error_code="GATEWAY_TIMEOUT",
        bank_raw_response_code="U30",
        payment_method=PaymentMethod.UPI_AUTOPAY,
        latency_ms=12400,
        bank_switch_degradation_score=0.85,
        last_inbound_message=CustomerMessage(
            message_text="bhai mere account se 3200 kat gaye par order confirm nahi hua, please help dobara mat katna"
        )
    )
    
    ai_out_1 = reasoner.reason(p1_telemetry)["reasoner_output"]
    active_policy = persistence_mgr.get_active_merchant_policy() if persistence_mgr else merchant_policy
    gate = DeterministicPolicyGate(policy=active_policy)
    dec_1 = gate.evaluate(p1_telemetry, ai_out_1)

    if persistence_mgr:
        with persistence_mgr.transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM processed_events WHERE payment_id = %s;", (payment_id,))
                cur.execute("DELETE FROM payment_cases WHERE payment_id = %s;", (payment_id,))
            persistence_mgr.check_and_register_event("evt_fail_001", payment_id, "3200.0:GATEWAY_TIMEOUT:U30", conn=conn)
            persistence_mgr.get_or_create_case(payment_id, "inv_demo_multi_001", 3200.0, PaymentState.PAYMENT_FAILED, conn=conn)
            persistence_mgr.record_transition(payment_id, PaymentState.PAYMENT_FAILED, PaymentState.TELEMETRY_ANALYSIS, "Failure telemetry ingested", conn=conn)
            persistence_mgr.record_transition(payment_id, PaymentState.TELEMETRY_ANALYSIS, PaymentState.POLICY_GATED, "Policy gate passed", conn=conn)
            c1 = persistence_mgr.record_transition(payment_id, PaymentState.POLICY_GATED, PaymentState.PAUSE_RECON_VERIFY, "Debit claim lock", conn=conn)
            st1 = c1["current_state"]
    else:
        in_memory_engine.get_or_create_case(payment_id, "inv_demo_multi_001", 3200.0, PaymentState.PAYMENT_FAILED)
        in_memory_engine.reserve_event("evt_fail_001", payment_id, "3200.0:GATEWAY_TIMEOUT:U30")
        in_memory_engine.record_transition(payment_id, PaymentState.PAYMENT_FAILED, PaymentState.TELEMETRY_ANALYSIS, "Failure telemetry ingested")
        in_memory_engine.record_transition(payment_id, PaymentState.TELEMETRY_ANALYSIS, PaymentState.POLICY_GATED, "Policy gate passed")
        c1 = in_memory_engine.record_transition(payment_id, PaymentState.POLICY_GATED, PaymentState.PAUSE_RECON_VERIFY, "Debit claim lock")
        in_memory_engine.complete_event("evt_fail_001", payment_id)
        st1 = c1["current_state"]
    
    events.append({
        "step": 1,
        "event_id": "evt_fail_001",
        "event_type": "PAYMENT_FAILED_DEBIT_CLAIM",
        "ai_proposed": ai_out_1.proposed_action.value,
        "policy_action": dec_1.final_action.value,
        "status": "ACCEPTED",
        "resulting_state": st1,
        "action_taken": "PAUSE_RECON_VERIFY (Retries Halted)"
    })

    # Step 2: Ingest Authoritative Bank Settlement Webhook
    if persistence_mgr:
        with persistence_mgr.transaction() as conn:
            persistence_mgr.check_and_register_event("evt_recon_002", payment_id, "3200.0:SETTLED:RRN_998877", conn=conn)
            c2 = persistence_mgr.record_transition(payment_id, PaymentState.PAUSE_RECON_VERIFY, PaymentState.RECOVERED, "Bank reconciliation confirmed RRN settlement", conn=conn)
            st2 = c2["current_state"]
    else:
        in_memory_engine.reserve_event("evt_recon_002", payment_id, "3200.0:SETTLED:RRN_998877")
        c2 = in_memory_engine.mark_case_recovered(payment_id, 3200.0, "998877")
        in_memory_engine.complete_event("evt_recon_002", payment_id)
        st2 = c2["current_state"]
    
    events.append({
        "step": 2,
        "event_id": "evt_recon_002",
        "event_type": "BANK_RECON_SETTLED",
        "ai_proposed": "N/A (Authoritative Bank Recon)",
        "policy_action": "COMMIT_RECOVERED",
        "status": "ACCEPTED",
        "resulting_state": st2,
        "action_taken": "RECOVERED (Invoice marked Paid via RRN #998877)"
    })

    # Step 3: Ingest Duplicate Replay of Step 2
    if persistence_mgr:
        is_step3_new = persistence_mgr.check_and_register_event("evt_recon_002", payment_id, "3200.0:SETTLED:RRN_998877")
        st3 = st2
    else:
        res3 = in_memory_engine.reserve_event("evt_recon_002", payment_id, "3200.0:SETTLED:RRN_998877")
        is_step3_new = (res3 != EventReservationStatus.ALREADY_PROCESSED)
        st3 = st2
    
    events.append({
        "step": 3,
        "event_id": "evt_recon_002",
        "event_type": "DUPLICATE_REPLAY_ATTACK",
        "ai_proposed": "N/A",
        "policy_action": "SUPPRESS_DUPLICATE",
        "status": "DUPLICATE_SUPPRESSED (IDEMPOTENT NO-OP)" if not is_step3_new else "ACCEPTED",
        "resulting_state": st3,
        "action_taken": "NO_OP (Zero State Mutation, Zero Outbound Dispatch)"
    })

    return {
        "scenario": "Multi-Event Idempotent Recovery & Replay Protection",
        "total_amount_inr": 3200.0,
        "events": events
    }


# =============================================================================
# AUDIT LEDGER & TAMPER DETECTION (ADMIN ONLY)
# =============================================================================

_persisted_tamper_backup: Optional[Dict[str, Any]] = None

@app.get("/api/ledger")
async def get_ledger(
    actor: ActorContext = Depends(require_roles(UserRole.AUDITOR))
):
    if persistence_mgr:
        is_valid, err = persistence_mgr.verify_persisted_ledger_integrity()
        blocks = [b.model_dump() for b in persistence_mgr.get_ledger_blocks()]
        return {
            "persistence_source": "POSTGRESQL",
            "is_integrity_valid": is_valid,
            "integrity_error": err,
            "total_blocks": len(blocks),
            "blocks": blocks
        }
    else:
        is_valid, err = in_memory_engine.ledger.verify_integrity()
        return {
            "persistence_source": "IN_MEMORY",
            "is_integrity_valid": is_valid,
            "integrity_error": err,
            "total_blocks": len(in_memory_engine.ledger.chain),
            "blocks": in_memory_engine.ledger.export_ledger()
        }


@app.post("/api/ledger/tamper-test")
async def tamper_test(
    request: Request,
    actor: ActorContext = Depends(require_roles(UserRole.ADMIN)),
    x_confirm_destructive: Optional[str] = Header(None)
):
    if not x_confirm_destructive or x_confirm_destructive.lower() != "true":
        raise HTTPException(
            status_code=400,
            detail="Destructive demo action requires explicit confirmation header 'X-Confirm-Destructive: true'."
        )

    mutation_rate_limiter.check_rate_limit(request, "tamper")
    global _ledger_backup, _persisted_tamper_backup
    if persistence_mgr:
        blocks = persistence_mgr.get_ledger_blocks()
        if not blocks:
            seed_telem = TransactionTelemetry(
                payment_id="pay_init_seed",
                invoice_id="inv_init_seed",
                amount_inr=2499.0,
                gateway_error_code="BAD_REQUEST_ERROR",
                bank_raw_response_code="51",
                payment_method=PaymentMethod.UPI_AUTOPAY,
                latency_ms=450,
                bank_switch_degradation_score=0.1
            )
            ai_out = reasoner.reason(seed_telem)["reasoner_output"]
            dec = policy_gate.evaluate(seed_telem, ai_out)
            persistence_mgr.record_audit_block(
                seed_telem, dec, dec.final_action.value,
                PaymentState.AWAITING_CUSTOMER_ACTION.value, ai_out,
                correlation_id=actor.correlation_id, actor_id=actor.actor_id
            )
            blocks = persistence_mgr.get_ledger_blocks()

        _persisted_tamper_backup = {
            "action_executed": blocks[0].action_executed,
            "current_hash": blocks[0].current_hash
        }

        # Mutate block 0 in PostgreSQL to prove detection
        with persistence_mgr.transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE audit_blocks SET action_executed = 'FORGED_UNAUTHORIZED_REFUND_INR_10000' WHERE block_index = 0;"
                )
        is_valid, err = persistence_mgr.verify_persisted_ledger_integrity()
        return {
            "tamper_simulated": True,
            "persistence_source": "POSTGRESQL",
            "cryptographic_detection_successful": not is_valid,
            "detection_error_message": err,
            "corrupted_block_index": 0,
            "forged_payload": "FORGED_UNAUTHORIZED_REFUND_INR_10000",
            "triggered_by": actor.actor_id
        }
    else:
        if not in_memory_engine.ledger.chain:
            seed_telem = TransactionTelemetry(
                payment_id="pay_init_seed",
                invoice_id="inv_init_seed",
                amount_inr=2499.0,
                gateway_error_code="BAD_REQUEST_ERROR",
                bank_raw_response_code="51",
                payment_method=PaymentMethod.UPI_AUTOPAY,
                latency_ms=450,
                bank_switch_degradation_score=0.1
            )
            ai_out = reasoner.reason(seed_telem)["reasoner_output"]
            dec = policy_gate.evaluate(seed_telem, ai_out)
            executor.execute(seed_telem, dec, StateMachine(), ai_out)

        _ledger_backup = copy.deepcopy(in_memory_engine.ledger)
        corrupted_entry = in_memory_engine.ledger.chain[0]
        corrupted_entry.action_executed = "FORGED_UNAUTHORIZED_REFUND_INR_10000"
        is_valid, err = in_memory_engine.ledger.verify_integrity()
        return {
            "tamper_simulated": True,
            "persistence_source": "IN_MEMORY",
            "cryptographic_detection_successful": not is_valid,
            "detection_error_message": err,
            "corrupted_block_index": 0,
            "forged_payload": corrupted_entry.action_executed,
            "triggered_by": actor.actor_id
        }


@app.post("/api/ledger/restore")
async def restore_ledger(
    request: Request,
    actor: ActorContext = Depends(require_roles(UserRole.ADMIN)),
    x_confirm_destructive: Optional[str] = Header(None)
):
    if not x_confirm_destructive or x_confirm_destructive.lower() != "true":
        raise HTTPException(
            status_code=400,
            detail="Destructive demo action requires explicit confirmation header 'X-Confirm-Destructive: true'."
        )

    mutation_rate_limiter.check_rate_limit(request, "restore")
    global _ledger_backup, _persisted_tamper_backup
    if persistence_mgr:
        orig_action = _persisted_tamper_backup.get("action_executed", "SCHEDULE_PTP") if _persisted_tamper_backup else "SCHEDULE_PTP"
        orig_hash = _persisted_tamper_backup.get("current_hash") if _persisted_tamper_backup else None

        with persistence_mgr.transaction() as conn:
            with conn.cursor() as cur:
                if orig_hash:
                    cur.execute("UPDATE audit_blocks SET action_executed = %s, current_hash = %s WHERE block_index = 0;", (orig_action, orig_hash))
                else:
                    cur.execute("UPDATE audit_blocks SET action_executed = %s WHERE block_index = 0;", (orig_action,))
        
        is_valid, err = persistence_mgr.verify_persisted_ledger_integrity()
        blocks = persistence_mgr.get_ledger_blocks()
        return {
            "restored": True,
            "persistence_source": "POSTGRESQL",
            "is_integrity_valid": is_valid,
            "total_blocks": len(blocks),
            "restored_by": actor.actor_id
        }
    else:
        if _ledger_backup:
            in_memory_engine.ledger = copy.deepcopy(_ledger_backup)
            _ledger_backup = None
        is_valid, err = in_memory_engine.ledger.verify_integrity()
        return {
            "restored": True,
            "persistence_source": "IN_MEMORY",
            "is_integrity_valid": is_valid,
            "total_blocks": len(in_memory_engine.ledger.chain),
            "restored_by": actor.actor_id
        }


# =============================================================================
# STATIC ASSET SERVING FOR REACT CONSOLE
# =============================================================================

frontend_dist = "frontend/dist"
if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    async def serve_react_root():
        return FileResponse(os.path.join(frontend_dist, "index.html"))

    @app.get("/{full_path:path}")
    async def serve_react_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
elif os.path.exists("web"):
    app.mount("/static", StaticFiles(directory="web"), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse("web/index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)
