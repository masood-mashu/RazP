# Temporal signal and target feasibility

## Recommendation

Use horizon 1 as the primary early-warning experiment. Treat horizons 3 and 5 as exploratory because their held-out positive counts are too small for reliable headline claims. Defer a temporal GNN until the target has adequate support or the task is reformulated.

## Test support

| Horizon | Test rows | Test positives | Positive rate | Latest-three-step positive fraction |
|---:|---:|---:|---:|---:|
| 1 | 1,610 | 19 | 0.0118 | 0.684 |
| 3 | 2,955 | 11 | 0.0037 | 0.455 |
| 5 | 2,675 | 8 | 0.0030 | 0.375 |

## Interpretation

The graph-enhanced baseline showed its clearest signal at horizon 1 and little or no improvement at horizons 3 and 5. A temporal GNN should therefore be evaluated only as a controlled horizon-1 experiment, with the same causal cutoff snapshots and the actor-disjoint stress test.
