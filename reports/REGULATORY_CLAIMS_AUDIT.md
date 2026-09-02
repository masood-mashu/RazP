# Sentinel-Recover: Regulatory & Policy Classification Audit

**Document Version:** 1.0.0  
**Date:** 2026-09-02  
**Status:** APPROVED FOR SUBMISSION  
**Scope:** Strict legal and technical taxonomy separating external law, merchant product policy, and benchmark modeling assumptions.

---

## 1. Executive Taxonomy Framework

To maintain absolute scientific rigor and avoid misrepresenting internal heuristics as legal mandates, all constraints within Sentinel-Recover are categorized into three unambiguous tiers:

| Tier | Category | Description | Authority / Source |
| :--- | :--- | :--- | :--- |
| **Tier A** | **Verified External Regulation** | Statutorily binding rules under Indian regulatory frameworks. Violation carries regulatory penalty or license suspension. | TRAI, RBI, NPCI |
| **Tier B** | **Merchant / Product Safety Policy** | Internal business guardrails designed for financial safety, customer retention, and risk management. | Merchant Risk Ops Policy |
| **Tier C** | **Benchmark Modeling Assumption** | Empirical simulation parameters used for discrete-event benchmark evaluation. | Benchmark Dataset Design |

---

## 2. Granular Classification Matrix

### Category A: Verified External Regulations

#### 1. TRAI Quiet Hours (TCCCPR 2018)
- **Statutory Authority:** Telecom Regulatory Authority of India — Telecom Commercial Communications Customer Preference Regulations, 2018 (Section 12(1)(b)).
- **Legal Rule:** No commercial, transactional promotional, or recovery communication may be initiated to a customer between **21:00 (9:00 PM) and 09:00 (9:00 AM) Indian Standard Time (IST)**.
- **Enforcement in Sentinel:** Deterministic time check against IST timezone (`tz_offset = +5.5 hours`). All outbound payment links, SMS, or WhatsApp dispatches are suppressed (`ABSTAIN_DO_NOTHING`).
- **Code Reference:** `core/policy_gate.py` lines 105–124; tested in `tests/test_policy_gate_exhaustive.py`.

#### 2. RBI e-Mandate Pre-Debit Notification Framework
- **Statutory Authority:** Reserve Bank of India — Circulars on Processing of e-Mandates on Cards/UPI for Recurring Transactions (RBI/2019-20/55 & RBI/2020-21/74).
- **Legal Rule:** Customers must receive pre-debit notification at least 24 hours prior to actual charge; if a customer revokes or cancels a mandate, no automated recurring debits may be attempted against the token.
- **Enforcement in Sentinel:** If `mandate_status` is `REVOKED` or `EXPIRED`, automated retries are permanently blocked; Sentinel switches exclusively to interactive payment link creation.
- **Code Reference:** `core/policy_gate.py` lines 145–160; tested in `tests/test_red_team.py::test_redteam_revoked_mandate_retry_blocked`.

#### 3. NPCI UPI Deemed Success & Auto-Reversal Guidelines
- **Statutory Authority:** National Payments Corporation of India — UPI Circulars on Dispute Management and Settlement Turnaround Times (NPCI/UPI/OC-87 & Harmonisation of TT).
- **Legal Rule:** In scenarios of timeout or pending switch state (`U30`, `U19`), if debit has occurred at issuer bank, the transaction must not be subjected to blind automatic retries which cause double debit.
- **Enforcement in Sentinel:** Any customer assertion of debit or timeout with switch degradation forces `PAUSE_RECON_VERIFY` (30-minute lock) to await authoritative bank recon file.
- **Code Reference:** `core/policy_gate.py` lines 65–85; tested in `tests/test_policy_gate.py::test_debit_claim_forces_recon_lock`.

---

### Category B: Merchant / Product Safety Policies

#### 1. Max Contact Attempt Ceiling (<= 3 Attempts)
- **Classification:** **Merchant Product Policy** (NOT statutory law).
- **Business Rationale:** Prevents customer harassment, high WhatsApp business messaging fees, and spam reputation loss.
- **Rule:** A maximum of 3 recovery contact attempts per invoice before escalating to manual Human Operations.
- **Code Reference:** `core/schemas.py::MerchantPolicy.max_contact_attempts = 3`.

#### 2. Promise-to-Pay (PTP) Extension Horizon (<= 14 Days)
- **Classification:** **Merchant Financial Risk Policy** (NOT statutory law).
- **Business Rationale:** Prevents indefinite deferrals; ensures working capital predictability.
- **Rule:** PTP dates beyond 14 days are clipped or escalated to operations.
- **Code Reference:** `core/schemas.py::MerchantPolicy.max_ptp_extension_days = 14`.

#### 3. Zero-Discount / Zero-Price Waiver Policy
- **Classification:** **Merchant Revenue Protection Policy** (NOT statutory law).
- **Business Rationale:** Autonomous AI agents must never possess the authority to grant price concessions, discounts, or fee waivers.
- **Rule:** Strict immutable face value enforcement (`allow_discounts = False`). Any LLM-proposed discount is stripped.
- **Code Reference:** `core/policy_gate.py` lines 85–100; tested in `tests/test_money_invariant.py`.

#### 4. Bank Switch Degradation Circuit Breaker (>= 0.65)
- **Classification:** **Merchant Infrastructure Safety Policy** (NOT statutory law).
- **Business Rationale:** Halts immediate retries when issuer switches (e.g., SBI, HDFC) experience major outages, preventing cascade bounce penalties.
- **Rule:** Switch degradation score >= 0.65 forces `RETRY_BACKOFF` or `PAUSE_RECON_VERIFY`.
- **Code Reference:** `core/policy_gate.py` lines 130–145.

---

### Category C: Benchmark Modeling Assumptions

The following parameters are empirical cost assumptions used for offline ablation modeling:
- **SMS Cost:** ₹0.15 per message
- **WhatsApp Interactive Cost:** ₹0.50 per template
- **LLM Inference Cost:** ₹0.10 per call (Gemini Flash)
- **Bank Bounce Penalty:** ₹5.00 per rejected retry on degraded switch
- **Chargeback Penalty:** ₹50.00 dispute processing fee per double debit

---

## 3. Reviewer Verification Checklist

- [x] No internal policy (e.g., 3 contact attempts) is described as legal statute.
- [x] TRAI quiet hours are strictly attributed to TCCCPR 2018.
- [x] RBI e-mandate rules are accurately mapped to pre-debit / revocation requirements.
- [x] Financial invariant assertions are backed by code unit tests.
