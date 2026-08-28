"""Construct actor-time features from causally timestamped raw edges only."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def read_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--label-file", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    tx_step = {}
    with (args.raw_dir / "txs_features.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            tx_step[row["txId"].strip()] = int(row["Time step"])

    # Keep only causally timestamped edge events. Labels are deliberately not read.
    events = defaultdict(lambda: defaultdict(lambda: {"in": set(), "out": set()}))
    for filename, address_col, direction in [
        ("AddrTx_edgelist.csv", "input_address", "in"),
        ("TxAddr_edgelist.csv", "output_address", "out"),
    ]:
        tx_col = "txId"
        for row in read_rows(args.raw_dir / filename):
            tx_id = row[tx_col].strip()
            step = tx_step.get(tx_id)
            address = row[address_col].strip()
            if step is not None:
                events[address][step][direction].add(tx_id)

    observations = defaultdict(set)
    for row in read_rows(args.label_file):
        observations[row["address"].strip()].add(int(row["time_step"]))

    output = args.out_dir / "causal_actor_time_features.csv"
    fields = [
        "address", "time_step", "in_tx_count_t", "out_tx_count_t", "tx_count_t",
        "in_tx_count_last3", "out_tx_count_last3", "tx_count_last3",
        "in_tx_count_last5", "out_tx_count_last5", "tx_count_last5",
        "cumulative_in_tx_count", "cumulative_out_tx_count", "cumulative_tx_count",
        "active_timesteps_to_t", "active_last3_timesteps", "active_last5_timesteps",
    ]
    rows_written = 0
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for address in sorted(observations):
            timeline = events.get(address, {})
            seen_in, seen_out, seen_tx = set(), set(), set()
            for step in range(1, 50):
                current = timeline.get(step, {"in": set(), "out": set()})
                seen_in.update(current["in"])
                seen_out.update(current["out"])
                seen_tx.update(current["in"] | current["out"])
                if step not in observations[address]:
                    continue
                def window(lookback: int):
                    ins, outs, txs = set(), set(), set()
                    for s in range(max(1, step - lookback + 1), step + 1):
                        event = timeline.get(s, {"in": set(), "out": set()})
                        ins.update(event["in"])
                        outs.update(event["out"])
                        txs.update(event["in"] | event["out"])
                    return len(ins), len(outs), len(txs)
                i3, o3, t3 = window(3)
                i5, o5, t5 = window(5)
                row = {
                    "address": address,
                    "time_step": step,
                    "in_tx_count_t": len(current["in"]),
                    "out_tx_count_t": len(current["out"]),
                    "tx_count_t": len(current["in"] | current["out"]),
                    "in_tx_count_last3": i3,
                    "out_tx_count_last3": o3,
                    "tx_count_last3": t3,
                    "in_tx_count_last5": i5,
                    "out_tx_count_last5": o5,
                    "tx_count_last5": t5,
                    "cumulative_in_tx_count": len(seen_in),
                    "cumulative_out_tx_count": len(seen_out),
                    "cumulative_tx_count": len(seen_tx),
                    "active_timesteps_to_t": sum(bool(timeline.get(s)) for s in range(1, step + 1)),
                    "active_last3_timesteps": sum(bool(timeline.get(s)) for s in range(max(1, step - 2), step + 1)),
                    "active_last5_timesteps": sum(bool(timeline.get(s)) for s in range(max(1, step - 4), step + 1)),
                }
                writer.writerow(row)
                rows_written += 1

    manifest = {
        "approved_features": [field for field in fields if field not in {"address", "time_step"}],
        "construction": "reconstructed from AddrTx_edgelist.csv and TxAddr_edgelist.csv joined to txs_features.csv Time step",
        "causality_rule": "an event contributes only when its transaction timestep is <= the actor observation timestep",
        "excluded_inputs": [
            "wallets_classes.csv and wallets_features_classes_combined.csv class columns",
            "all supplied wallet lifetime, block-height, total, and count features",
            "all supplied transaction Local_feature_* and Aggregate_feature_* columns",
            "AddrAddr_edgelist.csv because it has no transaction or timestep key",
        ],
        "rows_written": rows_written,
        "status": "approved_for_preprocessing_only; not yet a model result",
    }
    (args.out_dir / "causal_feature_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (args.out_dir / "causal_feature_manifest.md").write_text(
        "# Causal actor-time feature manifest\n\n"
        "These features are reconstructed from timestamped raw edges and transaction timesteps. "
        "They do not use labels or global wallet statistics.\n\n"
        + "Approved features:\n\n" + "\n".join(f"- `{x}`" for x in manifest["approved_features"])
        + "\n\nExcluded until proven causal:\n\n" + "\n".join(f"- {x}" for x in manifest["excluded_inputs"])
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
