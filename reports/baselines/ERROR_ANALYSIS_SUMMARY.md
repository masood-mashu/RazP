# XGBoost baseline error analysis

Source: `xgboost_error_analysis.json`, using the corrected temporal-continuation test data only.

## Findings

- Horizon-1 average precision is `0.0202` against a test positive rate of `0.0118`.
- Horizon-3 average precision is `0.0078` against a test positive rate of `0.0037`.
- Horizon-5 average precision is `0.0052` against a test positive rate of `0.0030`.
- At top-50 alerts, precision is 0% for horizon 1, 2.0% for horizon 3, and 0% for horizon 5.
- The model ranks better than chance but does not yet provide a high-precision alert queue.
- Test positives remain concentrated late in the timeline; horizon 1 has 10 of 19 positives at timestep 48. This makes the current held-out evaluation statistically fragile.
- Predicted probabilities are overconfident. For example, horizon-1 predictions in the 0.5+ score bin have an observed positive rate of only about 2.6%.
- The most important features are cumulative and recent transaction activity, which is directionally plausible but not evidence of causal risk by itself.

## Decision

Do not add a temporal GNN yet. First perform target-quality review:

1. Inspect positive and negative construction by timestep.
2. Quantify the remaining late-timestep concentration.
3. Add prevalence-normalized top-K and alert-volume metrics.
4. Calibrate scores on validation data.
5. Decide whether actor-level prediction is viable or whether transaction-level future prediction is better supported by the labels.
