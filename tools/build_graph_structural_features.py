"""Build causal graph-structural actor-time features from timestamped bipartite edges."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--observation-file", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    tx_step = {}
    for row in rows(args.raw_dir / "txs_features.csv"):
        tx_step[row["txId"].strip()] = int(row["Time step"])

    inputs = defaultdict(set)
    outputs = defaultdict(set)
    for row in rows(args.raw_dir / "AddrTx_edgelist.csv"):
        inputs[row["txId"].strip()].add(row["input_address"].strip())
    for row in rows(args.raw_dir / "TxAddr_edgelist.csv"):
        outputs[row["txId"].strip()].add(row["output_address"].strip())

    # Events contain only contemporaneous counterparties from each transaction.
    events = defaultdict(lambda: defaultdict(lambda: {"in": set(), "out": set(), "cp": set()}))
    for tx_id in set(inputs) | set(outputs):
        step = tx_step.get(tx_id)
        if step is None:
            continue
        ins, outs = inputs[tx_id], outputs[tx_id]
        for address in ins:
            events[address][step]["in"].add(tx_id)
            events[address][step]["cp"].update(outs - {address})
        for address in outs:
            events[address][step]["out"].add(tx_id)
            events[address][step]["cp"].update(ins - {address})

    observations = defaultdict(set)
    for row in rows(args.observation_file):
        observations[row["address"].strip()].add(int(row["time_step"]))

    output = args.out_dir / "graph_structural_actor_time_features.csv"
    fields = ["address", "time_step", "in_degree_t", "out_degree_t", "unique_counterparties_t", "unique_counterparties_last3", "unique_counterparties_last5", "new_counterparties_t", "cumulative_unique_counterparties"]
    written = 0
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for address in sorted(observations):
            timeline = events.get(address, {})
            seen = set()
            for step in range(1, 50):
                current = timeline.get(step, {"in": set(), "out": set(), "cp": set()})
                before = set(seen)
                seen.update(current["cp"])
                if step not in observations[address]:
                    continue
                def cps(lookback):
                    result = set()
                    for s in range(max(1, step - lookback + 1), step + 1):
                        result.update(timeline.get(s, {"cp": set()})["cp"])
                    return result
                cp3, cp5 = cps(3), cps(5)
                writer.writerow({
                    "address": address, "time_step": step,
                    "in_degree_t": len(current["in"]), "out_degree_t": len(current["out"]),
                    "unique_counterparties_t": len(current["cp"]), "unique_counterparties_last3": len(cp3),
                    "unique_counterparties_last5": len(cp5), "new_counterparties_t": len(current["cp"] - before),
                    "cumulative_unique_counterparties": len(seen),
                })
                written += 1
    manifest = {
        "features": fields[2:],
        "rows_written": written,
        "construction": "AddrTx and TxAddr joined to transaction timestep; counterparties are input/output addresses in the same transaction",
        "causality_rule": "only transactions at or before the observation timestep contribute",
        "excluded": "AddrAddr_edgelist.csv because it lacks transaction/timestep identity",
    }
    (args.out_dir / "graph_structural_feature_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
