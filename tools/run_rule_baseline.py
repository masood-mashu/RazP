"""Evaluate a deterministic activity rule on the leakage-safe actor-time data."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def read_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def pr_auc(labels, scores):
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    positives = sum(labels)
    if positives == 0:
        return None
    tp = fp = 0
    previous_recall = 0.0
    area = 0.0
    for i in order:
        if labels[i]:
            tp += 1
        else:
            fp += 1
        recall = tp / positives
        precision = tp / (tp + fp)
        area += (recall - previous_recall) * precision
        previous_recall = recall
    return area


def metrics(labels, scores, threshold):
    predictions = [score >= threshold for score in scores]
    tp = sum(p and y for p, y in zip(predictions, labels))
    fp = sum(p and not y for p, y in zip(predictions, labels))
    fn = sum((not p) and y for p, y in zip(predictions, labels))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"n": len(labels), "positives": sum(labels), "pr_auc": pr_auc(labels, scores), "threshold": threshold, "precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def best_threshold(labels, scores):
    candidates = sorted(set(scores), reverse=True)
    best = (0.0, candidates[-1] if candidates else 0.0)
    for threshold in candidates:
        result = metrics(labels, scores, threshold)
        if result["f1"] > best[0]:
            best = (result["f1"], threshold)
    return best[1] if candidates else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature-file", type=Path, required=True)
    parser.add_argument("--split-files", nargs=2, required=True)
    parser.add_argument("--out-file", type=Path, required=True)
    args = parser.parse_args()

    needed = ["tx_count_last3", "tx_count_last5", "active_last3_timesteps", "active_last5_timesteps"]
    features = {}
    for row in read_rows(args.feature_file):
        key = (row["address"], row["time_step"])
        features[key] = tuple(float(row[name]) for name in needed)

    all_results = {}
    for split_file in args.split_files:
        split_name = Path(split_file).stem
        rows_by_horizon = defaultdict(list)
        for row in read_rows(Path(split_file)):
            if row["split"] == "excluded":
                continue
            key = (row["address"], row["time_step"])
            values = features.get(key)
            if values is None:
                continue
            score = values[0] + values[1] + 0.5 * values[2] + 0.5 * values[3]
            for k in (1, 3, 5):
                if row[f"eligible_k{k}"] == "1":
                    rows_by_horizon[k].append((int(row[f"y_k{k}"]), score, row["split"]))

        result = {}
        for k, observations in rows_by_horizon.items():
            train = [(y, s) for y, s, split in observations if split == "train"]
            threshold = best_threshold([y for y, _ in train], [s for _, s in train])
            result[str(k)] = {
                split: metrics([y for y, s, actual in observations if actual == split], [s for y, s, actual in observations if actual == split], threshold)
                for split in ("train", "validation", "test")
            }
        all_results[split_name] = result

    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps({"rule": "tx_count_last3 + tx_count_last5 + 0.5*active_last3_timesteps + 0.5*active_last5_timesteps", "results": all_results}, indent=2), encoding="utf-8")
    print(json.dumps({"out_file": str(args.out_file), "results": all_results}, indent=2))


if __name__ == "__main__":
    main()
