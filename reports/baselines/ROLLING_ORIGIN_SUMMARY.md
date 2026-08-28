# Rolling-origin temporal evaluation

Five chronological folds were evaluated using the causal graph-enhanced XGBoost baseline. Each fold trains on an expanding history, validates on the next five timesteps, and tests on the following five timesteps.

| Horizon | Valid folds | Mean test average precision | Std. dev. |
|---:|---:|---:|---:|
| 1 | 5 | 0.0677 | 0.0793 |
| 3 | 5 | 0.0303 | 0.0276 |
| 5 | 4 | 0.0236 | 0.0268 |

## Decision

The signal is not stable enough to support a confident temporal-GNN headline claim. Horizon 1 is the only plausible research target, but its variance is high and some folds contain very few positives. Horizons 3 and 5 should remain exploratory.

The next model, if pursued, should be a narrowly scoped horizon-1 temporal GNN ablation, evaluated across the same rolling folds and compared directly with the graph-enhanced XGBoost baseline. It should not be presented as production-ready risk scoring.
