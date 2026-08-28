"""Streaming integrity audit for the locally acquired Elliptic++ dataset.

This audit intentionally does not train a model or create derived labels.
It checks file structure, row counts, IDs, labels, timesteps, nulls, and
cross-file references, then writes JSON and Markdown reports.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Iterable


EXPECTED = {
    "txs_features.csv": ["txId", "Time step"],
    "txs_classes.csv": ["txId", "class"],
    "txs_edgelist.csv": ["txId1", "txId2"],
    "wallets_features.csv": ["address", "Time step"],
    "wallets_classes.csv": ["address", "class"],
    "AddrAddr_edgelist.csv": ["input_address", "output_address"],
    "AddrTx_edgelist.csv": ["input_address", "txId"],
    "TxAddr_edgelist.csv": ["txId", "output_address"],
    "wallets_features_classes_combined.csv": ["address", "Time step", "class"],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def inspect_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        rows = 0
        empty_cells = 0
        empty_by_column: Counter[str] = Counter()
        for row in reader:
            rows += 1
            for column, value in row.items():
                if value is None or value.strip() == "":
                    empty_cells += 1
                    empty_by_column[column] += 1
    return {
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "rows": rows,
        "columns": len(header),
        "header": header,
        "empty_cells": empty_cells,
        "empty_by_column": dict(empty_by_column),
        "expected_columns_present": all(c in header for c in EXPECTED[path.name]),
    }


def collect_values(path: Path, key: str) -> tuple[set[str], Counter[str], Counter[str], int]:
    values: set[str] = set()
    duplicates: Counter[str] = Counter()
    invalid: Counter[str] = Counter()
    rows = 0
    for row in read_rows(path):
        rows += 1
        value = (row.get(key) or "").strip()
        if not value:
            invalid["empty"] += 1
        elif value in values:
            duplicates[value] += 1
        else:
            values.add(value)
    return values, duplicates, invalid, rows


def collect_txs(path: Path) -> tuple[set[str], Counter[str], Counter[str], Counter[str]]:
    ids: set[str] = set()
    steps: Counter[str] = Counter()
    invalid: Counter[str] = Counter()
    labels: Counter[str] = Counter()
    for row in read_rows(path):
        tx_id = (row.get("txId") or "").strip()
        step = (row.get("Time step") or "").strip()
        if not tx_id:
            invalid["empty_txId"] += 1
        elif tx_id in ids:
            invalid["duplicate_txId"] += 1
        else:
            ids.add(tx_id)
        try:
            step_value = int(step)
            steps[str(step_value)] += 1
        except ValueError:
            invalid["invalid_timestep"] += 1
    return ids, steps, invalid, labels


def collect_labels(path: Path, key: str) -> tuple[set[str], Counter[str], Counter[str]]:
    ids: set[str] = set()
    labels: Counter[str] = Counter()
    invalid: Counter[str] = Counter()
    for row in read_rows(path):
        item = (row.get(key) or "").strip()
        label = (row.get("class") or "").strip()
        if item in ids:
            invalid["duplicate_key"] += 1
        ids.add(item)
        labels[label] += 1
        if label not in {"1", "2", "3"}:
            invalid["invalid_label"] += 1
    return ids, labels, invalid


def edge_reference_check(path: Path, left: str, right: str, valid_left: set[str], valid_right: set[str]) -> dict:
    rows = 0
    invalid_left = 0
    invalid_right = 0
    duplicate_edges: Counter[tuple[str, str]] = Counter()
    for row in read_rows(path):
        rows += 1
        a = (row.get(left) or "").strip()
        b = (row.get(right) or "").strip()
        if a not in valid_left:
            invalid_left += 1
        if b not in valid_right:
            invalid_right += 1
        duplicate_edges[(a, b)] += 1
    return {
        "rows": rows,
        "invalid_left_references": invalid_left,
        "invalid_right_references": invalid_right,
        "duplicate_edge_rows": sum(n - 1 for n in duplicate_edges.values() if n > 1),
    }


def audit(root: Path) -> dict:
    files = {}
    missing = []
    for name in EXPECTED:
        path = root / name
        if not path.exists():
            missing.append(name)
        else:
            files[name] = inspect_file(path)

    report: dict = {"root": str(root), "missing_files": missing, "files": files}
    if missing:
        return report

    tx_features, tx_steps, tx_invalid, _ = collect_txs(root / "txs_features.csv")
    tx_labels, tx_label_counts, tx_label_invalid = collect_labels(root / "txs_classes.csv", "txId")
    wallet_features, wallet_feature_dupes, wallet_invalid, wallet_rows = collect_values(root / "wallets_features.csv", "address")
    wallet_labels, wallet_label_counts, wallet_label_invalid = collect_labels(root / "wallets_classes.csv", "address")

    wallet_label_map = {}
    for row in read_rows(root / "wallets_classes.csv"):
        wallet_label_map[(row.get("address") or "").strip()] = (row.get("class") or "").strip()
    combined_class_mismatches = 0
    combined_missing_addresses = 0
    for row in read_rows(root / "wallets_features_classes_combined.csv"):
        address = (row.get("address") or "").strip()
        combined_class = (row.get("class") or "").strip()
        if address not in wallet_label_map:
            combined_missing_addresses += 1
        elif combined_class != wallet_label_map[address]:
            combined_class_mismatches += 1

    # Wallet feature rows are temporal observations, so duplicate addresses are expected.
    address_time_keys: set[tuple[str, str]] = set()
    duplicate_address_time = 0
    wallet_steps: Counter[str] = Counter()
    for row in read_rows(root / "wallets_features.csv"):
        key = ((row.get("address") or "").strip(), (row.get("Time step") or "").strip())
        if key in address_time_keys:
            duplicate_address_time += 1
        address_time_keys.add(key)
        wallet_steps[key[1]] += 1
    wallet_feature_dupes_summary = {"duplicate_address_rows": sum(wallet_feature_dupes.values()), "duplicate_address_time_rows": duplicate_address_time}

    report["transactions"] = {
        "feature_ids": len(tx_features),
        "label_ids": len(tx_labels),
        "feature_label_id_difference": sorted(tx_features ^ tx_labels)[:20],
        "timesteps": {"values": sorted(map(int, tx_steps)), "counts": dict(tx_steps)},
        "invalid": {**tx_invalid, **tx_label_invalid},
        "label_counts": dict(tx_label_counts),
        "edge_references": edge_reference_check(root / "txs_edgelist.csv", "txId1", "txId2", tx_features, tx_features),
    }
    report["wallets"] = {
        "feature_rows": wallet_rows,
        "unique_addresses_in_features": len(wallet_features),
        "label_addresses": len(wallet_labels),
        "feature_label_address_difference": sorted(wallet_features ^ wallet_labels)[:20],
        "timesteps": {"values": sorted(int(x) for x in wallet_steps if x), "counts": dict(wallet_steps)},
        "invalid": {**wallet_invalid, **wallet_label_invalid},
        "label_counts": dict(wallet_label_counts),
        "duplicate_summary": wallet_feature_dupes_summary,
        "combined_class_mismatches": combined_class_mismatches,
        "combined_missing_addresses": combined_missing_addresses,
        "edge_references": {
            "AddrAddr": edge_reference_check(root / "AddrAddr_edgelist.csv", "input_address", "output_address", wallet_features, wallet_features),
            "AddrTx": edge_reference_check(root / "AddrTx_edgelist.csv", "input_address", "txId", wallet_features, tx_features),
            "TxAddr": edge_reference_check(root / "TxAddr_edgelist.csv", "txId", "output_address", tx_features, wallet_features),
        },
    }
    report["leakage_review"] = {
        "must_review_features": [
            "Aggregate_feature_1..Aggregate_feature_72",
            "in_txs_degree, out_txs_degree",
            "total_BTC, fees, size, num_input_addresses, num_output_addresses",
            "all wallet lifetime/block/total/count features",
            "wallets_classes.csv and wallets_features_classes_combined.csv labels",
        ],
        "reason": "The supplied data contains graph aggregates and global actor labels. Causality must be established before use in a future-window task.",
        "status": "review_required_before_modeling",
    }
    return report


def markdown(report: dict) -> str:
    lines = ["# Elliptic++ Dataset Audit", "", f"Raw directory: `{report['root']}`", ""]
    lines += ["## File inventory", "", "| File | Rows | Columns | Empty cells | SHA-256 |", "|---|---:|---:|---:|---|"]
    for name, item in report["files"].items():
        lines.append(f"| `{name}` | {item['rows']:,} | {item['columns']} | {item['empty_cells']:,} | `{item['sha256'][:16]}…` |")
    if report.get("missing_files"):
        lines += ["", "Missing files: " + ", ".join(report["missing_files"])]
        return "\n".join(lines) + "\n"
    tx = report["transactions"]
    wa = report["wallets"]
    lines += ["", "## Transaction checks", "", f"- Timesteps: `{tx['timesteps']['values']}`", f"- Labels: `{tx['label_counts']}`", f"- Feature/label ID mismatches reported: `{len(tx['feature_label_id_difference'])}` (sampled at 20)", f"- Empty transaction-feature cells: `{report['files']['txs_features.csv']['empty_cells']:,}`; columns: `{report['files']['txs_features.csv']['empty_by_column']}`", f"- Edge reference result: `{tx['edge_references']}`", "", "## Wallet checks", "", f"- Timesteps: `{wa['timesteps']['values']}`", f"- Labels: `{wa['label_counts']}`", f"- Feature rows: `{wa['feature_rows']:,}`; unique addresses: `{wa['unique_addresses_in_features']:,}`", f"- Duplicate address-time rows: `{wa['duplicate_summary']['duplicate_address_time_rows']:,}` (repeated observations require semantic review)", f"- Combined-file label mismatches: `{wa['combined_class_mismatches']:,}`; missing addresses: `{wa['combined_missing_addresses']:,}`", f"- Edge reference results: `{wa['edge_references']}`", "", "## Leakage review", "", "The audit does not approve supplied aggregates or global actor labels for modeling. They require a causal feature review before deriving future-window labels.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.raw_dir)
    args.report_dir.mkdir(parents=True, exist_ok=True)
    (args.report_dir / "ellipticplusplus_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (args.report_dir / "ellipticplusplus_audit.md").write_text(markdown(result), encoding="utf-8")
    print(json.dumps({"status": "ok", "report_dir": str(args.report_dir), "missing_files": result["missing_files"]}, indent=2))


if __name__ == "__main__":
    main()
