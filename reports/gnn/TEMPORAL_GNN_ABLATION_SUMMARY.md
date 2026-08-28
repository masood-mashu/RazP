# Horizon-1 temporal GNN ablation

## Setup

- One-layer mean GraphSAGE-style message passing.
- Same-timestep address neighborhoods reconstructed from timestamped bipartite transaction edges.
- Same 22 causal activity and structural features used by the graph-enhanced XGBoost baseline.
- Horizon-1 target only.
- Five expanding rolling-origin folds.
- No future edges, labels, global wallet labels, or untimestamped address-pair edges used as inputs.

## Result

| Model | Mean test average precision | Std. dev. |
|---|---:|---:|
| Graph-enhanced XGBoost | 0.0677 | 0.0793 |
| Temporal GNN ablation | 0.0650 | 0.0575 |

## Interpretation

The temporal GNN does not improve mean ranking over the simpler graph-enhanced XGBoost baseline. Its lower variance is worth noting, but the task is too sparse for a strong superiority claim. The current evidence favors the interpretable graph-enhanced XGBoost as the primary detector and the GNN as an experimental ablation.

This is a valid negative result: adding message passing did not automatically add value under the current target, features, and data regime.
