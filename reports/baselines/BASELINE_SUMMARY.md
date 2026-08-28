# Baseline summary

## Models

- Rule: activity score from recent transaction counts and active timesteps.
- XGBoost: 250 trees, depth 4, learning rate 0.05, fixed random seed 42, class weighting from the training split.
- Features: the 15 reconstructed causal actor-time features only.
- Thresholds were selected on validation data and then applied once to test data.

## Temporal-continuation test results after target correction

| Horizon | Rule average precision | XGBoost average precision | XGBoost precision | XGBoost recall |
|---:|---:|---:|---:|---:|
| 1 | 0.0071 | 0.0202 | 0.0077 | 0.1579 |
| 3 | 0.0027 | 0.0078 | 0.0132 | 0.0909 |
| 5 | 0.0026 | 0.0052 | 0.0047 | 0.7500 |

The reported `pr_auc` field is scikit-learn average precision, used here as the ranking metric for the highly imbalanced task. The target now requires a complete horizon and excludes windows containing unknown future activity.

## Interpretation

XGBoost improves ranking over the deterministic rule, but the operating-point precision is still low. The current task has only 19, 11, and 8 test positives for horizons 1, 3, and 5 in the temporal-continuation protocol. Results should therefore be treated as an initial baseline, not evidence of deployment readiness.

The actor-disjoint stress test is similarly sparse and shows weak transfer to unseen actors.

## Decision

The pipeline is reproducible and the first learned baseline is complete. Before adding graph models, perform error analysis, inspect positive/negative construction, and evaluate top-k alerting and calibration. Do not use these results as a final product claim.
