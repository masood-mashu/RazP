"""Create explicit actor-disjoint and temporal-continuation split manifests."""

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
    parser.add_argument("--label-file", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    first_step = {}
    for row in read_rows(args.raw_dir / "wallets_features.csv"):
        address = row["address"].strip()
        step = int(row["Time step"])
        first_step[address] = min(step, first_step.get(address, step))

    assignments = {}
    for address, step in first_step.items():
        if step <= 30:
            assignments[address] = "train"
        elif step <= 35:
            assignments[address] = "validation"
        else:
            assignments[address] = "test"

    membership_path = args.out_dir / "actor_split_membership.csv"
    with membership_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["address", "first_observed_timestep", "actor_disjoint_split"])
        for address in sorted(assignments):
            writer.writerow([address, first_step[address], assignments[address]])

    strict_path = args.out_dir / "actor_disjoint_temporal_rows.csv"
    continuation_path = args.out_dir / "temporal_continuation_rows.csv"
    strict_counts = {name: Counter() for name in ("train", "validation", "test")}
    continuation_counts = {name: Counter() for name in ("train", "validation", "test")}
    with strict_path.open("w", encoding="utf-8", newline="") as strict_handle, continuation_path.open("w", encoding="utf-8", newline="") as continuation_handle:
        fields = ["address", "time_step", "y_k1", "eligible_k1", "y_k3", "eligible_k3", "y_k5", "eligible_k5", "split"]
        strict_writer = csv.DictWriter(strict_handle, fieldnames=fields)
        continuation_writer = csv.DictWriter(continuation_handle, fieldnames=fields)
        strict_writer.writeheader()
        continuation_writer.writeheader()
        for row in read_rows(args.label_file):
            address = row["address"].strip()
            step = int(row["time_step"])
            actor_group = assignments.get(address)
            if actor_group is None:
                continue
            temporal_group = "train" if step <= 30 else "validation" if step <= 35 else "test"

            strict_split = actor_group if actor_group == temporal_group else "excluded"
            strict_row = dict(row)
            strict_row["split"] = strict_split
            if strict_split != "excluded":
                strict_writer.writerow(strict_row)
                strict_counts[strict_split]["rows"] += 1
                for k in (1, 3, 5):
                    if row[f"eligible_k{k}"] == "1":
                        strict_counts[strict_split][f"eligible_k{k}"] += 1
                        strict_counts[strict_split][f"positive_k{k}"] += int(row[f"y_k{k}"]) == 1

            continuation_row = dict(row)
            continuation_row["split"] = temporal_group
            continuation_writer.writerow(continuation_row)
            continuation_counts[temporal_group]["rows"] += 1
            for k in (1, 3, 5):
                if row[f"eligible_k{k}"] == "1":
                    continuation_counts[temporal_group][f"eligible_k{k}"] += 1
                    continuation_counts[temporal_group][f"positive_k{k}"] += int(row[f"y_k{k}"]) == 1

    summary = {
        "actor_counts": dict(Counter(assignments.values())),
        "strict_actor_disjoint_temporal": {name: dict(counts) for name, counts in strict_counts.items()},
        "temporal_continuation": {name: dict(counts) for name, counts in continuation_counts.items()},
        "strict_definition": "actor first-observed timestep determines membership; rows also must fall in the matching time range",
        "continuation_definition": "all actors retained; rows assigned only by timestep",
    }
    (args.out_dir / "split_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
