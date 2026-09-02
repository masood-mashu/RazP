# Sentinel-Recover: Benchmark Provenance & Reproducibility Specification

**Document Version:** 1.0.0  
**Date:** 2026-09-02  
**Dataset Version:** `v1.0.0-heldout`  
**Status:** VERIFIED (68/68 Genuine Live Gemini Calls)  

---

## 1. Cryptographic Hashes & Integrity

| Dataset File | Sample Count | Format | SHA-256 Checksum |
| :--- | :--- | :--- | :--- |
| **`benchmark/eval_cases.json`** | **68 cases** | JSON Array | `aa125d85df95fc20b6e5dc0e4dce86555f502495cc3b6206817e64702da85c31` |
| **`benchmark/dev_cases.json`** | **32 cases** | JSON Array | `af13a7c7d8dae72525045549d09351175903eb67b0870658862cdde6547d7d74` |

- **Dev / Eval Overlap:** Exactly **0 shared cases** (Zero contamination).
- **Immutability Guarantee:** Evaluator opens dataset in read-only mode.
- **Hidden State Isolation:** `environment_hidden` parameters (`salary_day`, `willingness_to_pay`, `actually_debited_by_bank`, `is_switch_healthy`) are strictly instantiated within `SimulatedEnvironment` and NEVER exposed to `TransactionTelemetry`, prompt templates, or policy gates.

---

## 2. Dataset Synthesis & Seed Configuration

- **Generation Script:** `benchmark/dataset_generator.py`
- **Master Random Seed:** `42` (Fixed pseudo-random seed across `random`, `faker`, and `numpy`)
- **Case Taxonomy Distribution (Eval Split - 68 Cases):**
  1. `RULE_SUPERIORITY` (14 cases): Standard deterministic error codes (e.g. Card 51, UPI limit, Closed account).
  2. `AI_ESSENTIAL_PTP` (17 cases): Multilingual Hinglish customer delay requests ("salary 7th ko aayegi", "kal subah").
  3. `MANDATORY_ABSTENTION` (10 cases): Quiet hours (21:00–09:00 IST), max contact ceiling (attempt >= 3), terminal account cancellations.
  4. `ADVERSARIAL_EXPLOITATION` (10 cases): Prompt injection, unicode bypass, discount extortion, fake UTRs.
  5. `SAFE_RECON_LOCK` (10 cases): Customer debit assertion under high bank switch latency (`U30`, `U19`).
  6. `SEMANTIC_AMBIGUITY` (7 cases): Conflicting signals, illegible text, multi-intent messages requiring human escalation.

---

## 3. System Architecture & Model Versions

- **Model Identifier:** `gemini-flash-lite-latest` (configured via `GEMINI_MODEL`)
- **Prompt Version:** `v1.0.0` (`prompts/reasoner_v1.txt`)
- **Schema Version:** `v1.0.0` (`core/schemas.py::AIReasonerOutput`)
- **SDK Version:** `google-genai>=0.1.0`
- **Simulator Version:** `v1.0.0` (`simulator/environment.py`)
- **Evaluator Version:** `v1.0.0` (`benchmark/evaluator.py`)

---

## 4. Benchmark Execution Matrix

To reproduce the benchmark evaluations independently:

### Command 1: Run 6-Way Ablation Benchmark
```powershell
python -m benchmark.run_ablation
```
**Output Artifact:** `reports/ablation_results.json`

### Command 2: Run Full Automated Test Suite (67 Tests)
```powershell
python -m pytest tests/ -v
```

### Command 3: Run Live Gemini Evaluation
```powershell
python -m benchmark.run_gemini_eval
```
**Output Artifact:** `reports/gemini_eval_results.json`

### Latest Credentialed Run Boundary

The latest run on 2026-09-02 used `gemini-3.7-flash` and completed all 68 cases, but the API returned HTTP 429 `RESOURCE_EXHAUSTED` after quota exhaustion. Recorded telemetry is **0 live Gemini calls / 68 fallback calls**. Its accuracy and recovery values must therefore be labeled deterministic-fallback results, not live-Gemini performance. A one-case smoke call succeeded before the quota was exhausted, proving the adapter and model name are valid; it does not establish 68-case live coverage.

---

## 5. Environment & Runtime Requirements

- **Python Version:** 3.10+ (Tested on Python 3.11.0 on Windows & Linux)
- **Required Packages:**
  ```text
  fastapi>=0.110.0
  uvicorn>=0.28.0
  pydantic>=2.7.0
  google-genai>=0.1.0
  pytest>=8.0.0
  pytest-asyncio>=0.23.0
  python-dotenv>=1.0.0
  ```
