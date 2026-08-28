# Graph baseline summary

The first graph baseline augments the 15 causal activity features with seven causal structural features: in/out degree, unique counterparties over current/3/5-step windows, new counterparties, and cumulative unique counterparties.

## Temporal-continuation test

| Horizon | Causal XGBoost AP | Graph-enhanced XGBoost AP | Graph precision | Graph recall |
|---:|---:|---:|---:|---:|
| 1 | 0.0202 | 0.0696 | 0.0429 | 0.6842 |
| 3 | 0.0078 | 0.0123 | 0.0058 | 0.0909 |
| 5 | 0.0052 | 0.0046 | 0.0017 | 0.1250 |

## Interpretation

Graph structure adds useful short-term signal at horizon 1. The gain does not persist at horizons 3 and 5, and absolute alert precision remains low. The result supports investigating a temporal graph model, but does not justify claiming a production-ready detector.

The actor-disjoint stress test shows the same pattern: a meaningful horizon-1 ranking signal but weak longer-horizon transfer.

## Next gate

Before implementing a temporal GNN, establish whether the horizon-3/5 target is intrinsically too sparse or whether richer temporal features are needed. Any neural graph result must use the same cutoff snapshots and corrected labels.
