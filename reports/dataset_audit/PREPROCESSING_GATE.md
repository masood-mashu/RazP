# Temporal preprocessing gate

Status: labels and split manifests generated; feature approval still pending.

## Generated artifacts

- `data/processed/temporal_contract/actor_early_warning_labels.csv`
- `data/processed/temporal_contract/feature_causality_manifest.json`
- `data/processed/temporal_contract/temporal_label_summary.json`
- `data/processed/temporal_contract/splits/actor_split_membership.csv`
- `data/processed/temporal_contract/splits/actor_disjoint_temporal_rows.csv`
- `data/processed/temporal_contract/splits/temporal_continuation_rows.csv`
- `data/processed/temporal_contract/splits/split_summary.json`

## Target

For an address observed at timestep `t`, the target is 1 when the address is linked through `AddrTx_edgelist.csv` or `TxAddr_edgelist.csv` to a known class-1 transaction in the future horizon. A target is eligible only when the future window contains at least one known class-1 or class-2 transaction; unknown-only windows are excluded.

## Split decision

The strict actor-disjoint split is retained as an inductive stress test. Its test set contains only 18, 26, and 30 positives for horizons 1, 3, and 5, respectively. This is too small for a stable headline comparison.

The temporal-continuation split is the provisional primary protocol because it better represents monitoring recurring entities and provides more positives. It must use causal snapshot construction and explicitly report actor overlap.

## Remaining hard gate

No feature is approved yet. The next step is to audit the construction window of every supplied feature and build actor-time features from past transaction and edge data only. Global wallet labels, lifetime totals, and supplied aggregate fields remain excluded until proven causal.

No model training is permitted until this feature-causality gate is complete.
