# RazP: Autonomous Zero-Loss Payment Recovery Engine
### Guardrailed Neuro-Symbolic Payment Recovery Engine — Razorpay AI Buildathon 2026 (Track 03)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136+-009688.svg)](https://fastapi.tiangolo.com)
[![Pytest](https://img.shields.io/badge/pytest-67%20passed%20(100%25)-brightgreen.svg)](https://docs.pytest.org)
[![Gemini](https://img.shields.io/badge/AI%20Reasoner-Gemini%20Flash--Lite%20(v1.0.0)-8E44AD.svg)](file:///d:/hackathon/RazorPay/core/gemini_reasoner.py)
[![Audit Ledger](https://img.shields.io/badge/Audit%20Ledger-SHA--256%20Chained-success.svg)](file:///d:/hackathon/RazorPay/core/ledger.py)
[![GitHub](https://img.shields.io/badge/GitHub-masood--mashu%2FRazP-181717.svg)](https://github.com/masood-mashu/RazP)

---

## 1. Problem Statement & Core Thesis

> **“Given a failed payment and all available evidence, determine the safest next recovery action and execute it within hard financial, communication, and regulatory constraints.”**

In Indian payment ecosystems (UPI AutoPay, Mandates, Cards), payment failures degrade across non-linear failure modes: ambiguous gateway timeouts, messy multilingual Hinglish customer communications, bank switch degradation, and deemed-success race conditions.

Standard industry rule engines either spam degraded bank switches or fail to parse natural language commitments, leaving recoverable revenue on the table while triggering customer chargebacks. Unconstrained LLMs hallucinate unauthorized discounts and violate TRAI quiet hours.

**RazP** implements a guardrailed neuro-symbolic architecture: **Gemini Flash performs unstructured semantic interpretation and proposes structured actions**, while an **authoritative deterministic spine owns money, policy, quiet hours, state transitions, idempotency, and cryptographic audit non-repudiation**.

---

## 2. Clear Boundary: AI vs. Deterministic Responsibilities

| Responsibility Domain | Gemini Semantic Reasoner (AI Zone) | Deterministic Spine (Zero AI Zone) |
|---|:---:|:---:|
| **Multilingual Language Parsing** | **Active** (Hinglish/Hindi/English code-switching) | ❌ No |
| **Noisy Telemetry Disambiguation** | **Active** (Latency + Bank Codes + Switch Health) | ❌ No |
| **Action Proposal** | **Active** (Proposes from finite action space) | ❌ No |
| **Financial Arithmetic & Invoices** | ❌ **Forbidden** (Cannot touch amounts or discounts) | **Authoritative (Immutable)** |
| **TRAI Quiet Hours (21:00–09:00 IST)** | ❌ **Forbidden** (No clock override authority) | **Authoritative (IST Enforced)** |
| **Max Contact & Retry Limits** | ❌ **Forbidden** (Cannot bypass contact ceiling $\le 3$) | **Authoritative (Circuit Breaker)** |
| **State Machine Lifecycle & Status** | ❌ **Forbidden** (Cannot directly declare `RECOVERED`) | **Authoritative (FSM Transitions)** |
| **Webhook Replay Idempotency** | ❌ **Forbidden** | **Authoritative (SHA-256 Event Gate)** |
| **Audit Ledger & Non-Repudiation** | ❌ **Forbidden** | **Authoritative (Hash Chained)** |

---

## 3. Invariant Neuro-Symbolic Pipeline

```
Observable Failure Telemetry + Inbound Customer Message
                         │
                         ▼
        [Gemini Flash Semantic Reasoner]
    (Model: gemini-flash-lite-latest | Prompt: v1.0.0)
                         │
                         ▼ (Raw Structured JSON Proposal)
   [Pydantic Schema Validation & Typing: AIReasonerOutput]
                         │
                         ▼ (Strict Parameter Allow-List & Constraint Verification)
   [Deterministic Policy Gate (TRAI Quiet Hours, 0% Discounts, Max 3 Attempts, Recon Lock)]
                         │
                         ▼ (Approved or Overridden PolicyDecision)
   [Deterministic Action Executor & State Machine (Idempotent Webhook Deduplication)]
                         │
                         ▼
   [Cryptographic SHA-256 Hash-Chained Audit Ledger]
```

---

## 4. Benchmark & Ablation Results (68 Held-Out Cases)

Evaluated on immutable [`benchmark/eval_cases.json`](file:///d:/hackathon/RazorPay/benchmark/eval_cases.json) (Dataset SHA-256: `aa125d85df95fc20b6e5dc0e4dce86555f502495cc3b6206817e64702da85c31`, ₹311,950 at risk):

### A. Architectural Ablation Matrix (Offline Baselines)
```
==================================================================================================================
Configuration                              Action Acc   Recovery Rate   Gross INR Rec   Unsafe Exec    Chargebacks 
==================================================================================================================
A. Simple Rule Baseline                     16.18%        14.71%         INR   58,750.00         0            10
B. Advanced Rule Baseline (Rule + Regex)    57.35%        29.41%         INR  117,750.00         0             4
C. Pure LLM (Unconstrained Proposal)        75.00%        48.53%         INR  180,920.00        18             0
D. LLM + Schema Validation                  75.00%        48.53%         INR  180,920.00        18             0
E. LLM + Deterministic Policy Gate          89.71%        48.53%         INR  190,370.00         0             0
F. Full Sentinel-Recover (Baseline)         89.71%        48.53%         INR  190,370.00         0             0
==================================================================================================================
```

### B. Genuine Live Gemini Benchmark Performance (100% Live API)
* **Model:** `gemini-flash-lite-latest` (Google GenAI SDK 2.13.0)
* **Live Coverage:** **68 / 68 Live Calls (0 Fallbacks, 0 API Errors)**
* **Action Accuracy:** **95.59%** (65 / 68 optimal actions)
* **Root Cause Diagnosis Macro-F1:** **1.0000**
* **Multilingual PTP Extraction Accuracy:** **100.0%** (MAE: 1.00 day)
* **Unsafe Executions:** **0** (100% intercepted by Policy Gate)
* **Disaster Chargebacks:** **0**
* **Telemetry Evidence:** [`reports/GEMINI_LIVE_EVAL.md`](file:///d:/hackathon/RazorPay/reports/GEMINI_LIVE_EVAL.md) & [`reports/gemini_eval_results.json`](file:///d:/hackathon/RazorPay/reports/gemini_eval_results.json)

---

## 5. Repository Structure

```
d:/hackathon/RazorPay/
├── core/
│   ├── schemas.py              # Strict Pydantic schemas (Telemetry, Actions, Policies, States)
│   ├── gemini_reasoner.py      # Production google-genai adapter with native response_schema
│   ├── policy_gate.py          # Deterministic safety gate (Quiet hours, rate limits, zero discounts)
│   ├── state_machine.py        # FSM with transition invariants & SHA-256 event deduplication
│   ├── baselines.py            # Simple Rules, Advanced Rules (Regex), and Pure-LLM baselines
│   ├── executor.py             # Deterministic action dispatcher & operational cost accountant
│   └── ledger.py               # Cryptographic SHA-256 hash-chained audit ledger
├── prompts/
│   └── reasoner_v1.txt         # Production versioned system prompt (v1.0.0)
├── simulator/
│   └── environment.py          # Seeded deterministic customer & bank simulation engine
├── benchmark/
│   ├── dataset_generator.py    # 100-case generator (32 dev + 68 eval across 6 categories)
│   ├── dev_cases.json          # 32 Fixed Development Cases
│   ├── eval_cases.json         # 68 Fixed Held-Out Evaluation Cases
│   ├── evaluator.py            # Component-level & end-to-end metrics calculator
│   ├── run_ablation.py         # 6-way ablation benchmark runner
│   └── run_gemini_eval.py      # Live Gemini evaluation runner with provenance tracking
├── server/
│   └── app.py                  # FastAPI server with live evaluation, multi-event, and tamper APIs
├── web/                        # Razorpay Payment Operations & Risk Console
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── tests/                      # 67 Automated unit, integration, invariant, and red-team tests
│   ├── test_ablation_5way.py
│   ├── test_baselines.py
│   ├── test_benchmark.py
│   ├── test_gemini_reasoner.py
│   ├── test_ledger.py
│   ├── test_ledger_security.py
│   ├── test_money_invariant.py
│   ├── test_policy_gate.py
│   ├── test_policy_gate_exhaustive.py
│   ├── test_reasoner.py
│   ├── test_red_team.py
│   ├── test_schemas_and_validation.py
│   ├── test_server_and_multi_event.py
│   ├── test_simulator_independence.py
│   └── test_state_machine.py
├── DEMO_RUNBOOK.md             # 8-10 Minute Reviewer Demonstration Walkthrough
└── reports/
    ├── ablation_results.json   # Raw 6-way benchmark telemetry
    ├── gemini_eval_results.json# Live Gemini evaluation telemetry
    ├── GEMINI_LIVE_EVAL.md     # Gemini evaluation provenance report
    ├── FINAL_RED_TEAM_AUDIT.md # Adversarial engineering audit report
    └── GEMINI_INTEGRATION_AUDIT.md # Initial SDK & boundary audit
```

---

## 6. Quick Start & Execution Guide

### 1. Run Complete Automated Test Suite (67 Tests in ~5s):
```powershell
python -m pytest tests/ -v
```

### 2. Run the 6-Way Benchmark & Ablation Study:
```powershell
python -m benchmark.run_ablation
```

### 3. Run Gemini Evaluation (live when quota is available; otherwise explicitly reported fallback):
```powershell
python -m benchmark.run_gemini_eval
```

### 4. Launch the Interactive Reviewer Console:
```powershell
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser and click **`⚡ RUN REVIEWER DEMO`** or follow [`DEMO_RUNBOOK.md`](file:///d:/hackathon/RazorPay/DEMO_RUNBOOK.md).
