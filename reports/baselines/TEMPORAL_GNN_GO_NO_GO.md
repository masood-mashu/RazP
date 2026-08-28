# Temporal GNN go/no-go decision

## Decision

Do not present a temporal GNN as the headline model yet.

A controlled horizon-1 GNN ablation is technically permissible, but the current target is too sparse and late-concentrated for a reliable claim. Horizons 3 and 5 should remain exploratory only.

## Evidence

- Temporal-continuation test positives: 19 at horizon 1, 11 at horizon 3, and 8 at horizon 5.
- 68.4% of horizon-1 test positives occur in the latest three available timesteps.
- The graph-enhanced XGBoost gain is strong at horizon 1 but weak at horizons 3 and 5.
- Actor-disjoint evaluation is also too small for stable model ranking.

## Next decision gate

Before investing in a temporal GNN, choose one of:

1. reformulate the target around a better-supported event unit;
2. use rolling-origin evaluation across multiple temporal folds;
3. proceed only with a clearly labeled horizon-1 research ablation and confidence intervals.

The current results are sufficient to guide this choice, not to claim production-grade early-warning performance.
