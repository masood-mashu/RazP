# Elliptic++ Dataset Audit

Raw directory: `data\raw\ellipticplusplus\Elliptic++ Dataset`

## File inventory

| File | Rows | Columns | Empty cells | SHA-256 |
|---|---:|---:|---:|---|
| `txs_features.csv` | 203,769 | 184 | 16,405 | `2db326ec8ddb68f1…` |
| `txs_classes.csv` | 203,769 | 2 | 0 | `013a11742969071a…` |
| `txs_edgelist.csv` | 234,355 | 2 | 0 | `a35053ba68a98e43…` |
| `wallets_features.csv` | 1,268,260 | 57 | 0 | `317daca2810c355d…` |
| `wallets_classes.csv` | 822,942 | 2 | 0 | `4e5132c99f941666…` |
| `AddrAddr_edgelist.csv` | 2,868,964 | 2 | 0 | `ffba894458e262a6…` |
| `AddrTx_edgelist.csv` | 477,117 | 2 | 0 | `f5f903f752387f66…` |
| `TxAddr_edgelist.csv` | 837,124 | 2 | 0 | `9f5afbdde7bc3d91…` |
| `wallets_features_classes_combined.csv` | 1,268,260 | 58 | 0 | `99bf27f7b76d6578…` |

## Transaction checks

- Timesteps: `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49]`
- Labels: `{'3': 157205, '2': 42019, '1': 4545}`
- Feature/label ID mismatches reported: `0` (sampled at 20)
- Empty transaction-feature cells: `16,405`; columns: `{'in_txs_degree': 965, 'out_txs_degree': 965, 'total_BTC': 965, 'fees': 965, 'size': 965, 'num_input_addresses': 965, 'num_output_addresses': 965, 'in_BTC_min': 965, 'in_BTC_max': 965, 'in_BTC_mean': 965, 'in_BTC_median': 965, 'in_BTC_total': 965, 'out_BTC_min': 965, 'out_BTC_max': 965, 'out_BTC_mean': 965, 'out_BTC_median': 965, 'out_BTC_total': 965}`
- Edge reference result: `{'rows': 234355, 'invalid_left_references': 0, 'invalid_right_references': 0, 'duplicate_edge_rows': 0}`

## Wallet checks

- Timesteps: `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49]`
- Labels: `{'2': 251088, '3': 557588, '1': 14266}`
- Feature rows: `1,268,260`; unique addresses: `822,942`
- Duplicate address-time rows: `347,569` (repeated observations require semantic review)
- Combined-file label mismatches: `0`; missing addresses: `0`
- Edge reference results: `{'AddrAddr': {'rows': 2868964, 'invalid_left_references': 0, 'invalid_right_references': 0, 'duplicate_edge_rows': 84620}, 'AddrTx': {'rows': 477117, 'invalid_left_references': 0, 'invalid_right_references': 0, 'duplicate_edge_rows': 0}, 'TxAddr': {'rows': 837124, 'invalid_left_references': 0, 'invalid_right_references': 0, 'duplicate_edge_rows': 0}}`

## Leakage review

The audit does not approve supplied aggregates or global actor labels for modeling. They require a causal feature review before deriving future-window labels.
