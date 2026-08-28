# Elliptic++ Phase 2 Dataset Contract

Status: audit complete; preprocessing is not yet approved.

## Accepted raw source

The raw files are the locally extracted Elliptic++ archive. The raw directory is immutable for this project:

`data/raw/ellipticplusplus/Elliptic++ Dataset/`

The official source is the Georgia Tech `git-disl/EllipticPlusPlus` repository and its linked Google Drive folder. The archive contains all eight canonical CSV files plus `wallets_features_classes_combined.csv`, a convenience table whose class column exactly matches `wallets_classes.csv` in the audit.

## Structural findings

- Transaction features and classes contain 203,769 matching transaction IDs.
- Transaction edges contain 234,355 rows with zero invalid references and zero duplicate edge rows.
- Wallet features contain 1,268,260 temporal observations for 822,942 unique addresses.
- Wallet classes contain 822,942 unique addresses.
- All transaction and wallet observations cover timesteps 1 through 49.
- Address-to-address edges contain 84,620 repeated address pairs. These are retained as interaction multiplicity until their temporal meaning is explicitly confirmed; they are not silently deduplicated.
- `txs_features.csv` contains 16,405 empty cells: exactly 965 rows missing all 17 blockchain-augmentation fields. These rows require an explicit missingness policy.

## Label policy

- `1` is illicit, `2` is licit, and `3` is unknown.
- Unknown is not a negative class and will not be used as a supervised negative example.
- Supplied global wallet labels are descriptive metadata only for the early-warning task. Future labels will be derived from time-indexed address-to-transaction links and known transaction labels.

## Leakage policy

Before any model is trained, we must audit every candidate feature for temporal causality. In particular, supplied aggregate features, lifetime/block/count features, global wallet labels, and the combined wallet table are not automatically eligible as prediction-time inputs.

The primary evaluation split must be actor-disjoint and temporal. A temporal-continuation split may be reported secondarily, with address overlap explicitly measured.

## Next preprocessing gate

1. Map each transaction and wallet observation to timestep.
2. Derive future-window actor targets for horizons 1, 3, and 5.
3. Exclude windows with insufficient observed future activity from supervised evaluation.
4. Produce a feature-causality manifest: `safe`, `unsafe`, or `needs-review` with evidence.
5. Build actor-disjoint and temporal-continuation split manifests.
6. Run split-level leakage checks and class-balance reports.

No modeling code should be added until this gate passes.
