# Gemini Integration Audit & Production Architecture

**Audit Date:** 2026-09-01  
**Auditor:** Sentinel-Recover Engineering  
**Scope:** `core/reasoner.py`, `core/schemas.py`, `core/policy_gate.py`, `benchmark/`, `tests/`

---

## 1. Current Implementation & SDK Analysis

1. **SDK in Use:**
   - The repository imports `from google import genai` (`google-genai` version `2.13.0` installed in the Python 3.11 environment).
2. **Current Model Name:**
   - The legacy hardcoded fallback in `core/reasoner.py` was corrected to the working default `gemini-3.7-flash`; `GEMINI_MODEL` remains supported.
3. **API Key Discovery:**
   - Looks for `GEMINI_API_KEY` or `GOOGLE_API_KEY`.
   - When no API key is present, it silently falls back to `_heuristic_reason()`.
4. **Structured Output Enforcement at SDK Boundary:**
   - Currently passes `"response_mime_type": "application/json"`, but does **NOT** yet pass `"response_schema": SemanticReasonerOutput` Pydantic class to `client.models.generate_content`.
   - This means JSON formatting is requested, but strict schema typing is only verified *post-generation* via Pydantic parsing rather than constrained decoding at the model decoding layer.

---

## 2. Current Data Flow & Boundary Isolation

```
[TransactionTelemetry + InboundMessage] (Observable Only)
       │
       ▼
[Gemini Semantic Reasoner] (Model: GEMINI_MODEL or gemini-3.7-flash)
       │
       ▼ (Produces Raw JSON Proposal)
[Pydantic Structured Schema Validation: SemanticReasonerOutput]
       │
       ▼ (Strict Allow-List & Constraint Verification)
[Deterministic Policy Gate] (Quiet Hours, Rate Limits, Zero Discounts, Recon Lock)
       │
       ▼ (Approved / Overridden PolicyDecision)
[Deterministic Action Executor & State Machine] (Idempotent Webhook Deduplication)
       │
       ▼
[SHA-256 Chained Cryptographic Audit Ledger]
```

---

## 3. Benchmark Contamination & Information Leakage Audit

* **Hidden State Leakage Check:**
  - `benchmark/eval_cases.json` holds both `telemetry`, `environment_hidden`, and `ground_truth`.
  - In `benchmark/evaluator.py:87-98`, ONLY `telemetry` (and `eval_time`) is constructed and passed to `decide_fn`.
  - The model prompt (`core/reasoner.py:_build_prompt`) receives **zero** fields from `environment_hidden` (no `balance_inr`, `salary_day`, `willingness_to_pay`, `actually_debited_by_bank`, etc.) and **zero** fields from `ground_truth`.
  - **Verdict:** Zero leakage. Observable telemetry is strictly isolated.

* **Heuristic Fallback vs. Live API Distinction:**
  - In offline benchmark runs (without `GEMINI_API_KEY`), the reasoner uses `_heuristic_reason`.
  - In Phase 4, we will add an explicit evaluation runner (`benchmark/run_gemini_eval.py`) that requires an active Gemini client, logs live token latencies, and explicitly records fallback events if API network drops occur.

---

## 4. Safety & Security Verification: Can Gemini Bypass the Spine?

| Threat / AI Output Vector | Current Defense in Codebase | Status |
|---|---|:---:|
| **Hallucinated Discount Amount** | `DeterministicPolicyGate` strips any parameter not in `ALLOWED_PARAMETERS` for that action. | **SAFE** |
| **Attempt to Force `RECOVERED` State** | `StateMachine` transition matrix only allows `RECOVERED` from `PAUSE_RECON_VERIFY` or after settlement recon callback. | **SAFE** |
| **Midnight Outbound Messaging** | `DeterministicPolicyGate` converts timestamp to IST and blocks outbound messages between 21:00 and 09:00 IST (TRAI TCCCPR). | **SAFE** |
| **Exceeding Contact Limits** | `DeterministicPolicyGate` escalates to Human Ops once `attempt_count >= 3`. | **SAFE** |
| **Webhook Replay Attacks** | `StateMachine.check_and_register_event` deduplicates event payload hashes. | **SAFE** |

---

## 5. Exact Changes Recommended for Phase 2 & Phase 3

1. **Dedicated Gemini Adapter (`core/gemini_reasoner.py`):**
   - Clean, modular single-responsibility adapter.
   - Uses `google-genai` SDK with configurable `GEMINI_MODEL` (default: `gemini-3.7-flash`).

### Current Run Status

The adapter’s one-case live smoke test succeeded on `gemini-3.7-flash`. The subsequent 68-case credentialed run was quota-limited (HTTP 429), recording 0 live and 68 fallback calls. Aggregate fallback metrics are not live-Gemini evidence.
   - Uses native `response_schema` structured decoding with Pydantic model `SemanticReasonerOutput`.
   - Explicitly records execution metadata (`is_live_gemini: bool`, `latency_ms: float`, `fallback_used: bool`).
2. **Versioned Production Prompt (`prompts/reasoner_v1.txt`):**
   - Explicit role boundary: semantic classification only, no payment execution, no discount authority.
   - Clean, realistic few-shot examples for code-switching, typos, relative dates, and deemed-success claims without copying benchmark evaluation strings.
3. **Dedicated Real Gemini Evaluation Harness (`benchmark/run_gemini_eval.py`):**
   - Generates `reports/gemini_eval_results.json` and `reports/gemini_eval_summary.md`.
   - Distinguishes raw model proposal vs. final executed action.
