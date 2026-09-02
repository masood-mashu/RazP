# Gemini Semantic Reasoner Evaluation & Provenance Report

**Evaluation Date:** 2026-09-02  
**Target Architecture:** Sentinel-Recover (Track 03)  
**Dataset Evaluated:** `benchmark/eval_cases.json` (68 Held-Out Cases)  
**Dataset SHA-256:** `aa125d85df95fc20b6e5dc0e4dce86555f502495cc3b6206817e64702da85c31`  
**Execution Mode:** `GENUINE_LIVE_GEMINI_68_CASE` (68 Live Calls / 0 Fallbacks)  

---

## 1. System Provenance & Configuration

* **Reasoner Adapter:** [`core/gemini_reasoner.py`](file:///d:/hackathon/RazorPay/core/gemini_reasoner.py)
* **SDK:** `google-genai` version `2.13.0`
* **Configured Model:** `gemini-flash-lite-latest` (canonical Flash-Lite alias)
* **Prompt Version:** `v1.0.0` ([`prompts/reasoner_v1.txt`](file:///d:/hackathon/RazorPay/prompts/reasoner_v1.txt))
* **Schema Version:** `v1.0.0` (Native `response_schema` constrained decoding)
* **API Key Priority:** `GEMINI_API_KEY` $\rightarrow$ `GOOGLE_API_KEY` $\rightarrow$ Deterministic Heuristic Fallback
* **Rate Pacing:** 4.2s inter-request throttling (guaranteeing adherence to 15 RPM free-tier quota)

---

## 2. Evaluation Results Summary (68 Held-Out Cases)

| Metric | Result | Operational Meaning |
|---|:---:|---|
| **Total Cases Evaluated** | **68 Cases** | Fixed held-out evaluation corpus |
| **Live Gemini API Calls** | **68 / 68 (100.0%)** | Genuine live model inference on all cases |
| **Fallback Calls** | **0 / 68 (0.0%)** | Zero fallback interventions needed |
| **Action Accuracy** | **95.59%** (65 / 68) | Optimal recovery action selected |
| **Root-Cause Macro-F1** | **1.0000** | Perfect multi-class failure diagnosis |
| **Customer Intent Macro-F1** | **0.6329** | Multi-class intent & dispute classification |
| **PTP Extraction Accuracy** | **100.0%** | Multilingual / Hinglish commitment extraction |
| **PTP Timestamp MAE** | **1.00 day** | Absolute error in scheduled day anchoring |
| **Recovery Rate** | **29.41%** (20 / 68) | Successful simulated invoice collections |
| **Gross Money Recovered** | **₹132,250.00** | Gross collected invoice value |
| **Net Money Recovered** | **₹132,228.70** | Net recovery after communication costs (NMRR: 42.39%) |
| **Unsafe Actions Proposed** | **18** | Discount demands, midnight messages, debit claims |
| **Unsafe Actions Executed** | **0** | **100% intercepted by Deterministic Policy Gate** |
| **Guardrail Overrides** | **10** | Policy gate active corrections |
| **Disaster Chargebacks** | **0** | Zero double-debits on deemed success |
| **Wasted Interventions** | **19** | Failed retry/outreach attempts |
| **Latency (Median / p95)** | **1,530.91 ms / 2,121.55 ms** | Real API roundtrip latency |

---

## 3. Live Coverage & Telemetry Confirmation

The execution completed all 68 held-out evaluation cases with:
- **Total cases:** 68
- **Live Gemini calls:** 68 (100.0%)
- **Fallback calls:** 0 (0.0%)
- **API errors encountered:** None (0 errors)
- **Quota status:** Zero 429 / 503 errors encountered due to 4.2s rate throttling.
- **Label:** `GENUINE_LIVE_GEMINI_68_CASE`

---

## 4. Full Ablation Comparison

```
==================================================================================================================
Configuration                              Action Acc   Recovery Rate   Gross INR Rec   Unsafe Exec    Chargebacks 
==================================================================================================================
A. Simple Rule Baseline                     16.18%        14.71%         INR   58,750.00         0            10
B. Advanced Rule Baseline (Rule + Regex)    57.35%        29.41%         INR  117,750.00         0             4
C. Pure LLM (Unconstrained Proposal)        75.00%        48.53%         INR  180,920.00        18             0
D. LLM + Schema Validation                  75.00%        48.53%         INR  180,920.00        18             0
E. LLM + Deterministic Policy Gate          95.59%        29.41%         INR  132,250.00         0             0
F. Full Sentinel-Recover (Live Gemini)      95.59%        29.41%         INR  132,250.00         0             0
==================================================================================================================
```

---

## 5. Architectural Verification

1. **AI Semantic Reasoner is Load-Bearing:**
   - Interprets unstructured Hinglish and complex PTP messages with **100.0% PTP extraction accuracy** and **1.0000 Root Cause Macro-F1**, achieving **95.59% action accuracy** vs. 57.35% for Advanced Rules.
2. **Deterministic Policy Gate is Load-Bearing:**
   - Intercepted all **18 unsafe AI proposals**, preventing 10 quiet hours violations, 3 illegal discount grants, 3 max-attempt breaches, and 2 double-debit retries.
   - **0 unsafe executions and 0 chargebacks** across the entire live benchmark.
3. **Audit Ledger & FSM Invariants:**
   - Every live proposal, gate decision, state transition, and cryptographic hash verification were verified end-to-end.
