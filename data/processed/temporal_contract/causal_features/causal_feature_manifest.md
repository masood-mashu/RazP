# Causal actor-time feature manifest

These features are reconstructed from timestamped raw edges and transaction timesteps. They do not use labels or global wallet statistics.

Approved features:

- `in_tx_count_t`
- `out_tx_count_t`
- `tx_count_t`
- `in_tx_count_last3`
- `out_tx_count_last3`
- `tx_count_last3`
- `in_tx_count_last5`
- `out_tx_count_last5`
- `tx_count_last5`
- `cumulative_in_tx_count`
- `cumulative_out_tx_count`
- `cumulative_tx_count`
- `active_timesteps_to_t`
- `active_last3_timesteps`
- `active_last5_timesteps`

Excluded until proven causal:

- wallets_classes.csv and wallets_features_classes_combined.csv class columns
- all supplied wallet lifetime, block-height, total, and count features
- all supplied transaction Local_feature_* and Aggregate_feature_* columns
- AddrAddr_edgelist.csv because it has no transaction or timestep key
