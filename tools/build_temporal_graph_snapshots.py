"""Build partitioned causal heterogeneous graph snapshots for Elliptic++."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def read_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    tx_step = {}
    for row in read_rows(args.raw_dir / "txs_features.csv"):
        tx_step[row["txId"].strip()] = int(row["Time step"])

    tx_path = args.out_dir / "transaction_nodes_by_timestep.csv"
    with tx_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["txId", "time_step"])
        for tx_id, step in sorted(tx_step.items(), key=lambda item: (item[1], item[0])):
            writer.writerow([tx_id, step])

    address_steps = defaultdict(set)
    for filename, address_col in [("AddrTx_edgelist.csv", "input_address"), ("TxAddr_edgelist.csv", "output_address")]:
        for row in read_rows(args.raw_dir / filename):
            tx_id = row["txId"].strip()
            if tx_id in tx_step:
                address_steps[row[address_col].strip()].add(tx_step[tx_id])

    addr_path = args.out_dir / "address_nodes_by_timestep.csv"
    with addr_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["address", "time_step"])
        for address in sorted(address_steps):
            for step in sorted(address_steps[address]):
                writer.writerow([address, step])

    edge_counts = {"AddrTx": Counter(), "TxAddr": Counter()}
    for filename, address_col, left, right, edge_name in [
        ("AddrTx_edgelist.csv", "input_address", "address", "txId", "AddrTx"),
        ("TxAddr_edgelist.csv", "output_address", "txId", "address", "TxAddr"),
    ]:
        path = args.out_dir / f"{edge_name.lower()}_edges_by_timestep.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([left, right, "time_step"])
            for row in read_rows(args.raw_dir / filename):
                tx_id = row["txId"].strip()
                step = tx_step.get(tx_id)
                if step is None:
                    continue
                writer.writerow([row[address_col].strip(), tx_id, step])
                edge_counts[edge_name][step] += 1

    tx_counts = Counter(tx_step.values())
    address_count_by_step = Counter()
    with addr_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            address_count_by_step[int(row["time_step"])] += 1
    manifest = {
        "node_types": {"transaction": "transaction_nodes_by_timestep.csv", "address": "address_nodes_by_timestep.csv"},
        "edge_types": {"address_to_transaction": "addrtx_edges_by_timestep.csv", "transaction_to_address": "txaddr_edges_by_timestep.csv"},
        "cutoff_rule": "snapshot(t) includes rows with time_step <= t",
        "included_edges": "AddrTx and TxAddr only; both have transaction IDs that provide timestamps",
        "excluded_edges": {"AddrAddr_edgelist.csv": "no transaction or timestep key, therefore not causal for snapshot construction"},
        "timesteps": list(range(1, 50)),
        "transaction_nodes_by_timestep": dict(sorted(tx_counts.items())),
        "address_observations_by_timestep": dict(sorted(address_count_by_step.items())),
        "edge_rows_by_timestep": {name: dict(sorted(counts.items())) for name, counts in edge_counts.items()},
    }
    (args.out_dir / "snapshot_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (args.out_dir / "snapshot_manifest.md").write_text(
        "# Causal temporal graph snapshots\n\n"
        "A cutoff snapshot at timestep `t` is formed by filtering each partitioned file to `time_step <= t`. "
        "Only timestamped address-transaction edges are included.\n\n"
        "The actor-level future-window target remains the primary early-warning benchmark. "
        "Transaction-level classification is secondary diagnostic work and is not called early warning.\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
