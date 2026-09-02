# 6-Way Ablation Study: Sentinel-Recover

**Evaluated on:** 68 Held-Out Cases  
**Dataset Path:** `benchmark/eval_cases.json`  
**Dataset SHA-256:** `aa125d85df95fc20b6e5dc0e4dce86555f502495cc3b6206817e64702da85c31`  
**Execution Timestamp:** 2026-09-02  

---

## 1. 6-Way Ablation Matrix (Architectural Baselines)

The table below reflects the architectural ablation baselines executed on the standard 68-case benchmark:

| Metric | A. Simple Rule | B. Advanced Rule (Regex) | C. Pure LLM | D. LLM + Schema | E. LLM + Policy Gate | F. Full Sentinel (Baseline) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Action Accuracy (%)** | 16.18% | 57.35% | 75.00% | 75.00% | 89.71% | **89.71%** |
| **Root-Cause Macro-F1** | 0.00 | 0.00 | 0.9625 | 0.9625 | 0.9625 | **0.9625** |
| **PTP Extraction Accuracy (%)** | 0.0% | 0.0% | 75.0% | 75.0% | 75.0% | **75.0%** |
| **Recovery Rate (%)** | 14.71% | 29.41% | 48.53% | 48.53% | 48.53% | **48.53%** |
| **Gross Money Recovered** | ₹58,750.00 | ₹117,750.00 | ₹180,920.00 | ₹180,920.00 | ₹190,370.00 | **₹190,370.00** |
| **Net ₹ Recovered (after costs)** | ₹58,244.50 | ₹117,239.00 | ₹180,899.20 | ₹180,899.20 | ₹190,347.70 | **₹190,347.70** |
| **Net Money Recovered Ratio (NMRR)** | 18.67% | 37.58% | 57.99% | 57.99% | 61.02% | **61.02%** |
| **Unsafe Actions Executed** | 0 | 0 | 🚨 **18** | 🚨 **18** | **0** | **0** |
| **Guardrail Interventions** | 0 | 0 | 0 | 0 | **10** | **10** |
| **Disaster Chargebacks** | 🚨 **10** | 🚨 **4** | 0 | 0 | **0** | **0** |
| **Wasted Interventions** | 21 | 22 | 26 | 26 | **16** | **16** |

---

## 2. Live Gemini Reasoner Performance (Live API Run)

When integrated with the live Google Gemini API (`gemini-flash-lite-latest`), Sentinel-Recover achieves:

* **Action Accuracy:** **95.59%** (65 / 68)
* **Root-Cause Macro-F1:** **1.0000**
* **PTP Extraction Accuracy:** **100.0%**
* **PTP Date MAE:** **1.00 day**
* **Live Calls:** **68 / 68 (100% Genuine Live)**
* **Unsafe Actions Executed:** **0** (100% intercepted by Policy Gate)
* **Disaster Chargebacks:** **0**
* **Telemetry Details:** See [`reports/GEMINI_LIVE_EVAL.md`](file:///d:/hackathon/RazorPay/reports/GEMINI_LIVE_EVAL.md) and [`reports/gemini_eval_results.json`](file:///d:/hackathon/RazorPay/reports/gemini_eval_results.json).

---

## 3. Key Findings

1. **Why Pure LLM is Dangerous:** Pure LLM executes **18 illegal actions** (granting 20% discounts to hostile customers, messaging during TRAI quiet hours, retrying on debit claims).
2. **Why Schema Validation Alone Fails:** Schema validation (Config D) guarantees syntactically valid JSON types, but allows all **18 regulatory, financial, and policy violations** to execute.
3. **Where Sentinel-Recover Wins:** The Deterministic Policy Gate (Config E & F) intercepts 100% of illegal actions, eliminating disaster chargebacks and margin leakage while boosting live action accuracy to **95.59%**.
