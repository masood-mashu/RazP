"""Review censoring and unknown-label contamination in early-warning targets."""

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
    parser.add_argument("--observation-file", type=Path, required=True)
    parser.add_argument("--out-file", type=Path, required=True)
    args = parser.parse_args()

    tx_step = {}
    for row in read_rows(args.raw_dir / "txs_features.csv"):
        tx_step[row["txId"].strip()] = int(row["Time step"])
    tx_label = {}
    for row in read_rows(args.raw_dir / "txs_classes.csv"):
        tx_label[row["txId"].strip()] = int(row["class"])

    # Per address and timestep: counts of known illicit, known licit, unknown events.
    events = defaultdict(lambda: defaultdict(Counter))
    for filename, address_col in [("AddrTx_edgelist.csv", "input_address"), ("TxAddr_edgelist.csv", "output_address")]:
        for row in read_rows(args.raw_dir / filename):
            tx_id = row["txId"].strip()
            step = tx_step.get(tx_id)
            if step is not None:
                events[row[address_col].strip()][step][str(tx_label.get(tx_id, 3))] += 1

    observations = {(row["address"].strip(), int(row["time_step"])) for row in read_rows(args.observation_file)}
    summary = {"observations": len(observations), "horizons": {}}
    by_step = {str(k): Counter() for k in (1, 3, 5)}
    for k in (1, 3, 5):
        counts = Counter()
        for address, step in observations:
            full_window = step + k <= 49
            future = Counter()
            for s in range(step + 1, min(step + k, 49) + 1):
                future.update(events[address].get(s, Counter()))
            known = future["1"] + future["2"]
            illicit = future["1"]
            unknown = future["3"]
            if full_window:
                counts["full_window"] += 1
                if known:
                    counts["full_window_known_eligible"] += 1
                    counts["full_window_positive"] += illicit > 0
                    counts["full_window_unknown_contaminated"] += unknown > 0
                if known and unknown == 0:
                    counts["fully_observed_eligible"] += 1
                    counts["fully_observed_positive"] += illicit > 0
            else:
                counts["right_censored"] += 1
            by_step[str(k)].update({str(step): int(illicit > 0) if full_window and known else 0})
        summary["horizons"][str(k)] = dict(counts)
        summary["positive_rate_among_full_window_eligible"] = summary["horizons"][str(k)].get("full_window_positive", 0) / max(1, summary["horizons"][str(k)].get("full_window_known_eligible", 0))

    summary["positive_by_observation_timestep"] = {k: dict(v) for k, v in by_step.items()}
    summary["recommendation"] = {
        "remove_right_censored_windows": True,
        "primary_label_policy": "full future horizon required; known illicit is positive; known licit with no unknown is negative; windows containing unknown future events are excluded",
        "reason": "Unknown is not a negative label, and truncating horizons creates inconsistent lookahead lengths.",
    }
    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
