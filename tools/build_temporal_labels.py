"""Build leakage-safe actor-time early-warning labels and a feature review manifest."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def load_transaction_metadata(root: Path):
    step_by_tx = {}
    label_by_tx = {}
    with (root / "txs_features.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            step_by_tx[row["txId"].strip()] = int(row["Time step"])
    with (root / "txs_classes.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            label_by_tx[row["txId"].strip()] = int(row["class"])
    return step_by_tx, label_by_tx


def add_event(events, address: str, tx_id: str, step_by_tx, label_by_tx):
    step = step_by_tx.get(tx_id)
    label = label_by_tx.get(tx_id)
    if step is None or label not in {1, 2, 3}:
        return
    known, illicit, unknown = events[address][step]
    events[address][step] = (known or label in {1, 2}, illicit or label == 1, unknown or label == 3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.raw_dir
    args.out_dir.mkdir(parents=True, exist_ok=True)

    step_by_tx, label_by_tx = load_transaction_metadata(root)
    events = defaultdict(lambda: defaultdict(lambda: (False, False, False)))
    for filename, address_col, tx_col in [
        ("AddrTx_edgelist.csv", "input_address", "txId"),
        ("TxAddr_edgelist.csv", "output_address", "txId"),
    ]:
        for row in rows(root / filename):
            add_event(events, row[address_col].strip(), row[tx_col].strip(), step_by_tx, label_by_tx)

    # One actor-time row is the prediction unit. Repeated source observations
    # at the same address/timestep are intentionally collapsed for labeling.
    observations = set()
    for row in rows(root / "wallets_features.csv"):
        observations.add(((row["address"] or "").strip(), int(row["Time step"])))

    label_path = args.out_dir / "actor_early_warning_labels.csv"
    horizons = (1, 3, 5)
    counts = {str(k): {"positive": 0, "negative": 0, "excluded": 0} for k in horizons}
    with label_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["address", "time_step"]
        for k in horizons:
            fieldnames += [f"y_k{k}", f"eligible_k{k}"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for address, step in sorted(observations, key=lambda x: (x[1], x[0])):
            row = {"address": address, "time_step": step}
            timeline = events.get(address, {})
            for k in horizons:
                full_window = step + k <= 49
                future = [timeline.get(s, (False, False, False)) for s in range(step + 1, step + k + 1)] if full_window else []
                known_future = any(known for known, _, _ in future)
                illicit_future = any(illicit for _, illicit, _ in future)
                unknown_future = any(unknown for _, _, unknown in future)
                eligible = full_window and known_future and not unknown_future
                row[f"y_k{k}"] = int(illicit_future) if eligible else ""
                row[f"eligible_k{k}"] = int(eligible)
                if not eligible:
                    counts[str(k)]["excluded"] += 1
                elif illicit_future:
                    counts[str(k)]["positive"] += 1
                else:
                    counts[str(k)]["negative"] += 1
            writer.writerow(row)

    feature_manifest = []
    with (root / "txs_features.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        header = csv.DictReader(handle).fieldnames or []
    for name in header:
        if name in {"txId", "Time step"}:
            status, reason = "safe_identifier", "identifier or observation time"
        elif name.startswith("Aggregate_feature_"):
            status, reason = "needs_review", "supplied one-hop aggregate; temporal causality is not documented"
        elif name in {"in_txs_degree", "out_txs_degree", "total_BTC", "fees", "size", "num_input_addresses", "num_output_addresses", "in_BTC_min", "in_BTC_max", "in_BTC_mean", "in_BTC_median", "in_BTC_total", "out_BTC_min", "out_BTC_max", "out_BTC_mean", "out_BTC_median", "out_BTC_total"}:
            status, reason = "needs_review", "blockchain augmentation; retain missingness and verify snapshot causality"
        elif name.startswith("Local_feature_"):
            status, reason = "needs_review", "inherited Elliptic feature; exact construction window is not documented here"
        else:
            status, reason = "needs_review", "unclassified supplied feature"
        feature_manifest.append({"feature": name, "status": status, "reason": reason})

    (args.out_dir / "feature_causality_manifest.json").write_text(json.dumps(feature_manifest, indent=2), encoding="utf-8")
    summary = {
        "unique_actor_time_observations": len(observations),
        "known_transaction_ids": sum(label in {1, 2} for label in label_by_tx.values()),
        "known_illicit_transaction_ids": sum(label == 1 for label in label_by_tx.values()),
        "target_counts": counts,
        "target_definition": "known illicit transaction involving the address during the future horizon; unknown-only future windows are excluded",
        "label_source": "txs_classes.csv joined through AddrTx_edgelist.csv and TxAddr_edgelist.csv",
    }
    (args.out_dir / "temporal_label_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
