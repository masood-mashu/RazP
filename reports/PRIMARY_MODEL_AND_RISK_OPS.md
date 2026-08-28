# Primary model and risk-operations contract

## Primary detector

Use the causal graph-enhanced XGBoost model as the primary detector.

Why:

- It achieved rolling-origin mean average precision `0.0677` versus `0.0650` for the temporal GNN.
- It is easier to explain using activity and neighborhood features.
- It is cheaper and simpler to retrain and serve.
- The GNN did not demonstrate a reliable improvement under the current sparse target.

The temporal GNN remains a documented negative ablation, not the production path.

## Prediction contract

- Primary horizon: 1 timestep.
- Secondary horizons: 3 and 5 only for exploratory analysis.
- Inputs: 22 reconstructed causal activity and graph-structural features.
- Output: calibrated risk score plus model version, observation timestep, and feature snapshot ID.
- Unknown future activity is not treated as a negative outcome.

## Alert policy

Use a review-capacity policy rather than a universal probability threshold:

- `critical`: top 10 alerts per timestep or score above the validated critical threshold; hold for immediate review.
- `high`: next 40 alerts; queue for priority review.
- `monitor`: remaining scored entities; no automatic intervention.
- `insufficient_evidence`: missing or stale causal features; do not alert automatically.

The top-K budget must be reported with precision, recall, alert count, and estimated review load. Thresholds are selected on validation data only.

## Evidence shown to a reviewer

Every alert should show:

- address and observation timestep;
- risk score and risk band;
- recent transaction counts;
- recent and cumulative counterparties;
- active timestep history;
- whether the score is inside the validated operating range;
- explicit data-quality flags;
- model version and audit timestamp.

The explanation is evidence, not a claim that the model has proven criminal activity.

## Failure recovery

- Missing features: mark `insufficient_evidence`, do not impute silently.
- Model unavailable: fall back to a logged rules-only monitor mode; no automatic block.
- Duplicate alert: deduplicate by `(address, timestep, model_version)`.
- Score instability: retain the alert but downgrade to monitor and request human review.
- Unknown labels: keep the outcome unresolved; never count it as a correct negative.
- Reviewer capacity exceeded: retain only the validated top-K queue and log deferred alerts.

## Demo behavior

1. Ingest a timestep snapshot.
2. Build causal actor and graph features.
3. Score entities with graph-enhanced XGBoost.
4. Display the top-K queue with evidence and data-quality state.
5. Select one alert to show its temporal activity and neighborhood changes.
6. Simulate one recoverable failure, such as missing features or model timeout.
7. Show the safe fallback, audit entry, and absence of an automatic block.
8. Report measured precision/recall, average precision, alert volume, and review load.

No LLM is required for detection. An LLM may later summarize already-structured evidence, but it must not invent evidence or decide the enforcement action.
