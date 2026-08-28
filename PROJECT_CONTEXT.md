# Razorpay AI Builder 2026 — Track 2 Project Context

## Purpose of this document

This document gives Claude or another collaborator the complete project context from the beginning: why the project exists, which hackathon track we selected, what has been implemented, what the experiments show, how the demo works, and what remains before this can be considered production-ready.

Submission entry points:

- `README.md` — concise repository front door and run instructions.
- `ARCHITECTURE.md` — standalone architecture and AI-judgment explanation.
- `PITCH_SCRIPT.md` — timed five-minute presentation script.
- `DEMO_RUNBOOK.md` — live demonstration sequence.

## 1. Why we are building this

Financial platforms need to identify suspicious activity early, before an actor or network causes more harm. A simple fraud classifier usually answers: “Was this transaction fraudulent?” Our project asks a more operationally useful question:

> Given the transaction graph observed up to time `t`, which actors are likely to exhibit illicit activity in a future window?

The goal is not to automatically declare a person or address criminal. The goal is to rank emerging risk signals for analyst review, explain why an actor was surfaced, and fail safely when the model or evidence is unavailable.

This is a research prototype using the Elliptic++ public benchmark. It is not trained on Razorpay customer data and must not be presented as a production Razorpay detector.

## 2. Hackathon track

We selected:

> Razorpay AI Builder 2026 — Track 2: AI Risk Manager

Project concept:

> Temporal early-warning detection of emerging illicit activity in transaction networks.

The differentiator is the combination of:

- Temporal behavior: what changed recently?
- Graph structure: who is connected to whom?
- Future-oriented labels: does illicit activity appear later?
- Risk operations: how should analysts respond?
- Safety controls: no automatic blocking and explicit fallback behavior.

## 3. Core objectives

1. Build a leakage-safe temporal prediction task.
2. Preserve the graph and time structure of Elliptic++.
3. Compare simple rules, tabular ML, graph-enhanced ML, and a temporal GNN ablation.
4. Select a model based on rolling temporal evaluation rather than a single random split.
5. Convert model scores into a human-review workflow.
6. Demonstrate safe behavior for missing data, model outage, duplicate alerts, and capacity limits.
7. Keep the entire prototype reproducible offline.

## 4. Dataset and provenance

The Elliptic++ dataset was uploaded locally and extracted under:

`data/raw/ellipticplusplus/Elliptic++ Dataset`

The dataset audit and contract are documented in:

- `reports/dataset_audit/ellipticplusplus_audit.md`
- `reports/dataset_audit/ellipticplusplus_audit.json`
- `reports/dataset_audit/DATASET_CONTRACT.md`

The dataset contains transaction, address/actor, timestamp, graph, feature, and label information. The project preserves the original raw data and creates derived data under `data/processed/temporal_contract`.

Important provenance boundary:

- Elliptic++ is a public research benchmark.
- It is not Razorpay production traffic.
- There is no evidence that its label distribution, graph behavior, or operational volume matches Razorpay.
- Any production claim would require an authorized representative validation stream.

## 5. Target definition

The primary target is actor-level future illicit activity.

For each actor at timestep `t`, the pipeline asks whether illicit activity occurs in a future horizon:

- `k=1`: primary operational horizon
- `k=3`: exploratory horizon
- `k=5`: exploratory horizon

The target protocol is documented in:

- `reports/baselines/TARGET_PROTOCOL_DECISION.md`
- `reports/dataset_audit/PREPROCESSING_GATE.md`

Target rules:

- Features use information available up to timestep `t`.
- Full horizon availability is required.
- Unknown future activity is excluded from evaluation.
- Known illicit future activity is positive.
- Known licit/no-unknown future activity is negative.

Generated target files include:

- `data/processed/temporal_contract/actor_early_warning_labels.csv`
- `data/processed/temporal_contract/temporal_label_summary.json`
- `data/processed/temporal_contract/feature_causality_manifest.json`

## 6. Leakage-safe temporal evaluation

The main evaluation uses rolling temporal continuation folds. Training occurs earlier in time, validation occurs next, and testing occurs later.

The project also builds actor-disjoint temporal rows as a stress test. The primary evaluation is temporal continuation; actor-disjoint evaluation is secondary because it is more restrictive and asks a different generalization question.

Split artifacts:

- `data/processed/temporal_contract/splits/actor_split_membership.csv`
- `data/processed/temporal_contract/splits/actor_disjoint_temporal_rows.csv`
- `data/processed/temporal_contract/splits/temporal_continuation_rows.csv`
- `data/processed/temporal_contract/splits/split_summary.json`

Leakage controls include:

- No future labels in features.
- No random mixing of future rows into training.
- Cumulative features stop at the current timestep.
- Temporal graph snapshots only use available history.
- Threshold selection uses validation, not the held-out test window.

## 7. Feature and graph pipeline

Implemented derived features:

### Causal actor-time features

Examples:

- Transactions at the current timestep.
- Inbound/outbound activity.
- Activity in the last 3 and 5 timesteps.
- Cumulative activity up to the current timestep.
- Number of active timesteps.

Files:

- `tools/build_causal_actor_features.py`
- `data/processed/temporal_contract/causal_features/causal_actor_time_features.csv`

### Temporal graph snapshots

Files:

- `tools/build_temporal_graph_snapshots.py`
- `data/processed/temporal_contract/graph_snapshots/`

### Graph structural features

Examples:

- In-degree and out-degree.
- Unique counterparties.
- New counterparties.
- Recent and cumulative neighborhood growth.

Files:

- `tools/build_graph_structural_features.py`
- `data/processed/temporal_contract/graph_features/graph_structural_actor_time_features.csv`

## 8. Models evaluated

Implemented evaluation scripts:

- `tools/run_rule_baseline.py`
- `tools/run_xgboost_baseline.py`
- `tools/run_graph_xgboost_baseline.py`
- `tools/run_temporal_gnn_ablation.py`
- `tools/run_rolling_origin_evaluation.py`

Compared models:

1. Rules baseline.
2. Causal-feature XGBoost.
3. Graph-enhanced XGBoost.
4. Horizon-1 temporal GNN ablation.

The temporal GNN was intentionally kept as a narrowly scoped ablation. It was not allowed to expand the project before the simpler graph-enhanced baseline was measured.

## 9. Main measured outcome

Rolling-origin mean average precision:

| Model | Horizon-1 mean AP | Interpretation |
|---|---:|---|
| Graph-enhanced XGBoost | `0.0677` | Selected primary detector |
| Temporal GNN ablation | `0.0650` | Close, but not better |
| Causal-feature XGBoost | approximately `0.0202` | Weaker non-graph reference |
| Rules baseline | approximately `0.0071` | Operational floor |

Graph-enhanced XGBoost rolling-origin results:

- `k=1`: `0.0677 ± 0.0793`
- `k=3`: `0.0303 ± 0.0276`
- `k=5`: `0.0236 ± 0.0268`

Interpretation:

- Graph structure adds useful signal over causal tabular features.
- The temporal GNN does not justify replacing the simpler primary model.
- Performance is unstable across time windows.
- Average precision is low in absolute terms because the task is extremely imbalanced and early-warning positives are rare.
- The result supports a ranking/review prototype, not autonomous enforcement.

Reports:

- `reports/baselines/rolling_origin_evaluation.json`
- `reports/baselines/ROLLING_ORIGIN_SUMMARY.md`
- `reports/baselines/GRAPH_BASELINE_SUMMARY.md`
- `reports/gnn/temporal_gnn_ablation.json`
- `reports/gnn/TEMPORAL_GNN_ABLATION_SUMMARY.md`
- `reports/PRIMARY_MODEL_AND_RISK_OPS.md`

Evaluation context added for presentation:

- Horizon-1 pooled held-out test base rate: approximately `1.17%`.
- Horizon-3 pooled held-out test base rate: approximately `0.80%`.
- Horizon-5 pooled held-out test base rate: approximately `0.87%`.
- Horizon-1 rolling mean AP `0.0677` is approximately `5.8×` the pooled random baseline.
- On the primary held-out test window, precision@50 is `2.0%` and recall@50 is `5.3%`.
- These figures describe a rare-event ranking task; AP is not classification accuracy.

Artifacts:

- `tools/build_evaluation_artifacts.py`
- `reports/evaluation_metrics.json`
- `reports/evaluation_pr_curve.svg`

## 10. Selected operational policy

The selected model is graph-enhanced XGBoost at horizon 1.

Current prototype policy:

- Critical score: `>= 0.85` → human review.
- High score: `>= 0.5713` → human review.
- Below high threshold → monitor.
- Missing required evidence → insufficient evidence + human review.
- Automatic blocks → always `0`.
- Analyst capacity overflow → defer, never silently drop.
- Model unavailable → rules-only monitor.

The threshold `0.5713` was chosen using validation data only. The validation-only calibration is in:

- `tools/calibrate_operational_thresholds.py`
- `reports/risk_ops_threshold_calibration.json`
- `reports/RISK_OPS_THRESHOLD_POLICY.md`

## 11. Threshold stability finding

The threshold is not stable enough for production deployment. Given only `25` known positives across the rolling validation windows, any threshold estimate is inherently high-variance. This is a data-scarcity finding as much as a model finding, and it reinforces the decision to route alerts to human review rather than enable automatic action.

Across 5 rolling validation folds:

- Validation rows: `2,527`
- Known positives: `25`
- Threshold range: `0.0162` to `0.6620`
- Mean threshold: `0.3603`
- Threshold standard deviation: `0.2701`
- Coefficient of variation: approximately `0.75`

The gate is therefore:

> `RESEARCH_ONLY`

Full assessment:

- `tools/assess_threshold_stability.py`
- `reports/threshold_stability_assessment.json`
- `reports/PRODUCTION_VALIDATION_GATE.md`

## 12. Shadow mode and capacity proxy

Shadow mode scores rows without triggering any action. It was run over the full available eligible stream:

- Rows scored: `7,511`
- Timesteps: `48`
- High/critical signals: `2,004`
- Critical signals: `132`
- Actions triggered: `0`
- Automatic blocks: `0`

This shows that the current absolute threshold would create too much alert volume for a real analyst operation.

Because no authorized Razorpay traffic is available, a seeded distribution-preserving proxy was also generated:

- Proxy rows: `20,000`
- Operational batches: `40`
- Source: eligible Elliptic++ rows sampled with replacement.

Capacity experiment:

- 10 alerts per batch → indicative recall `33.3%`.
- 25 alerts per batch → indicative recall `50.8%`.
- 50 alerts per batch → indicative recall `63.3%`.
- 100 alerts per batch → indicative recall `75.8%`.

These are proxy-only results for queue-load testing. They are not Razorpay performance evidence.

Files:

- `tools/run_shadow_mode.py`
- `reports/shadow_mode_summary.json`
- `tools/build_validation_proxy.py`
- `tools/assess_capacity_policy.py`
- `data/processed/temporal_contract/validation_proxy_20k.csv`
- `reports/capacity_policy_assessment.json`
- `reports/VALIDATION_PROXY_NOTICE.md`

## 13. Risk-operations demo

Dashboard files:

- `demo/index.html`
- `demo/app.js`
- `demo/api-adapter.js`
- `demo/styles.css`
- `demo/data/risk_ops_snapshot.json`
- `demo/data/recorded_predictions.json`

The dashboard contains:

- Overview of measured model outcomes.
- Model selection comparison.
- Horizon comparison.
- Alert queue with 50 ranked recorded predictions.
- Actor score, band, evidence, action, and audit context.
- API connection mode.
- Live score form.
- Model-failure simulation.
- Contrast mode for presentation.

The queue uses recorded predictions for reproducibility. The live scoring form can send a feature vector to the inference API.

Presentation runbook:

- `DEMO_RUNBOOK.md`
- `reports/RISK_OPS_DEMO_READINESS.md`

## 14. API and inference implementation

Local API:

- `api/risk_api.py`
- `api/requirements.txt`

Endpoints:

- `GET /health`
- `GET /ready`
- `GET /metrics`
- `GET /alerts`
- `POST /score`

The API supports two behaviors:

1. Recorded queue serving from `demo/data/risk_ops_snapshot.json`.
2. Real-time horizon-1 inference when launched with the saved model artifact.

Saved model:

- `models/xgb_graph_horizon1.json`
- `models/xgb_graph_horizon1.metadata.json`

Training script:

- `tools/train_realtime_model.py`

Real-time behavior:

- Valid feature vectors receive a model score and risk band.
- Missing features return `insufficient_evidence`.
- Non-object features are rejected.
- Non-numeric and non-finite feature values are rejected.
- Requests above the body-size limit are rejected.
- Unknown actors without a matching record fall back to monitor with score `0.0`.

## 15. Tests completed

Run tests from the project root:

```powershell
& "C:\Users\Masood\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
```

Current result: 5 API safeguard tests pass.

Tests cover:

- API health and alert listing.
- Known actor scoring.
- Unknown actor monitor fallback.
- Missing address rejection.
- Invalid feature-object rejection.

The existing risk-operations simulator also covers duplicate suppression, missing feature behavior, capacity deferral, model outage fallback, and zero automatic blocks.

## 16. How to run the current demo

Open two PowerShell windows.

Dashboard window:

```powershell
cd D:\hackathon\RazorPay
& "C:\Users\Masood\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m http.server 8765 --directory demo
```

API window:

```powershell
cd D:\hackathon\RazorPay
& "C:\Users\Masood\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" api\risk_api.py --artifact demo\data\risk_ops_snapshot.json --model-file models\xgb_graph_horizon1.json --metadata-file models\xgb_graph_horizon1.metadata.json --port 8766
```

Open:

`http://127.0.0.1:8765/`

## 17. What remains to implement

### Required before any real deployment

1. Obtain an authorized, representative Razorpay-like validation stream.
2. Define the real label-generation process and label delay.
3. Recalibrate thresholds using representative traffic and analyst capacity.
4. Run the model in shadow mode against that stream.
5. Measure alert rate, recall, precision, drift, missing evidence, and latency by time window.
6. Add persistent alert storage and audit-log storage.
7. Add authentication and authorization to the API.
8. Add request rate limiting and structured production logging.
9. Add model/data version compatibility checks.
10. Add monitoring and alerting for model availability and feature drift.
11. Add model rollback and artifact integrity verification.
12. Conduct privacy, legal, security, and responsible-risk review.
13. Keep automatic blocks disabled until explicitly approved through a separate risk review.

### Recommended engineering improvements

1. Replace the simplified live-score form with a real feature-construction service.
2. Connect the dashboard alert-detail panel to `/score/{actor}` or a persistent alert endpoint.
3. Add API integration tests using an inference-enabled `RiskEngine`.
4. Add contract tests for the prediction artifact schema.
5. Add calibration plots and time-window drift visualizations.
6. Add analyst feedback simulation and alert lifecycle states.
7. Add containerization or a deployment configuration after security review.

### Optional research extensions

1. Compare against a better-calibrated temporal GNN.
2. Test multiple lead times with a clearer business interpretation.
3. Add synthetic UPI-style graph generation for scenario testing.
4. Study cold-start actors and unseen neighborhoods separately.
5. Evaluate top-K ranking metrics alongside average precision.

## 18. Important handoff instructions

When continuing this project:

- Do not train on future rows.
- Do not select thresholds using the held-out test set.
- Do not describe Elliptic++ results as Razorpay production performance.
- Do not enable automatic blocking.
- Treat the proxy stream as load-testing evidence only.
- Preserve raw data and existing processed artifacts.
- Prefer extending the current scripts and contracts over creating a second incompatible pipeline.
- Keep recorded mode available for reproducible demos.

## Current project status

The research prototype, measured model comparison, risk-operations surface, recorded prediction path, real-time inference API, threshold analysis, shadow-mode analysis, capacity proxy, documentation, and basic safeguards are implemented.

The main unresolved item is not a missing coding feature. It is the absence of an authorized representative validation stream and the resulting inability to make production accuracy or deployment claims.
