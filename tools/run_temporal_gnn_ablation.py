"""Narrow horizon-1 temporal GraphSAGE-style ablation across rolling folds."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from torch import nn


FEATURES = ["in_tx_count_t", "out_tx_count_t", "tx_count_t", "in_tx_count_last3", "out_tx_count_last3", "tx_count_last3", "in_tx_count_last5", "out_tx_count_last5", "tx_count_last5", "cumulative_in_tx_count", "cumulative_out_tx_count", "cumulative_tx_count", "active_timesteps_to_t", "active_last3_timesteps", "active_last5_timesteps", "in_degree_t", "out_degree_t", "unique_counterparties_t", "unique_counterparties_last3", "unique_counterparties_last5", "new_counterparties_t", "cumulative_unique_counterparties"]
FOLDS = [(20, 21, 25, 26, 30), (25, 26, 30, 31, 35), (30, 31, 35, 36, 40), (35, 36, 40, 41, 45), (39, 40, 44, 45, 49)]


class MeanGraphSAGE(nn.Module):
    def __init__(self, width: int):
        super().__init__()
        self.self_layer = nn.Linear(width, 24)
        self.neighbor_layer = nn.Linear(width, 24)
        self.output = nn.Linear(24, 1)

    def forward(self, x, edge_index):
        src, dst = edge_index
        aggregate = torch.zeros_like(x)
        aggregate.index_add_(0, dst, x[src])
        degree = torch.zeros(x.shape[0], device=x.device)
        degree.index_add_(0, dst, torch.ones(src.shape[0], device=x.device))
        aggregate = aggregate / degree.clamp_min(1).unsqueeze(1)
        hidden = torch.relu(self.self_layer(x) + self.neighbor_layer(aggregate))
        return self.output(hidden).squeeze(1)


def metrics(y, p, threshold):
    pred = (p >= threshold).astype(int)
    return {"rows": int(len(y)), "positives": int(y.sum()), "average_precision": float(average_precision_score(y, p)) if y.sum() else None, "precision": float(precision_score(y, pred, zero_division=0)), "recall": float(recall_score(y, pred, zero_division=0)), "f1": float(f1_score(y, pred, zero_division=0))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--base-file", type=Path, required=True)
    parser.add_argument("--graph-file", type=Path, required=True)
    parser.add_argument("--label-file", type=Path, required=True)
    parser.add_argument("--out-file", type=Path, required=True)
    args = parser.parse_args()
    torch.manual_seed(42)
    np.random.seed(42)

    labels = pd.read_csv(args.label_file)
    base = pd.read_csv(args.base_file)
    graph = pd.read_csv(args.graph_file)
    data = labels.merge(base.merge(graph, on=["address", "time_step"], how="inner", validate="one_to_one"), on=["address", "time_step"], how="inner", validate="one_to_one")
    data[FEATURES] = data[FEATURES].fillna(0.0).astype(np.float32)

    tx_step = dict(zip(pd.read_csv(args.raw_dir / "txs_features.csv", usecols=["txId", "Time step"])["txId"].astype(str), pd.read_csv(args.raw_dir / "txs_features.csv", usecols=["txId", "Time step"])["Time step"].astype(int)))
    inputs, outputs = defaultdict(set), defaultdict(set)
    for row in pd.read_csv(args.raw_dir / "AddrTx_edgelist.csv", dtype=str).itertuples(index=False):
        inputs[row.txId].add(row.input_address)
    for row in pd.read_csv(args.raw_dir / "TxAddr_edgelist.csv", dtype=str).itertuples(index=False):
        outputs[row.txId].add(row.output_address)
    pairs_by_step = defaultdict(set)
    for tx_id in set(inputs) | set(outputs):
        step = tx_step.get(tx_id)
        if step is None:
            continue
        for left in inputs[tx_id]:
            for right in outputs[tx_id]:
                if left != right:
                    pairs_by_step[step].add((left, right))
                    pairs_by_step[step].add((right, left))

    snapshot = {}
    for step, frame in data.groupby("time_step", sort=True):
        frame = frame.reset_index(drop=True)
        addresses = frame.address.tolist()
        index = {address: i for i, address in enumerate(addresses)}
        edges = [(index[a], index[b]) for a, b in pairs_by_step[int(step)] if a in index and b in index]
        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous() if edges else torch.empty((2, 0), dtype=torch.long)
        snapshot[int(step)] = (frame, torch.tensor(frame[FEATURES].to_numpy(), dtype=torch.float32), edge_index)

    results = []
    for fold_id, (train_end, val_start, val_end, test_start, test_end) in enumerate(FOLDS, 1):
        model = MeanGraphSAGE(len(FEATURES))
        optimizer = torch.optim.Adam(model.parameters(), lr=0.003, weight_decay=1e-4)
        train_frames = [snapshot[s] for s in snapshot if s <= train_end]
        train_positive = sum(int((frame["eligible_k1"] == 1).mul(frame["y_k1"]).sum()) for frame, _, _ in train_frames)
        train_eligible = sum(int((frame["eligible_k1"] == 1).sum()) for frame, _, _ in train_frames)
        pos_weight = torch.tensor([(train_eligible - train_positive) / max(1, train_positive)], dtype=torch.float32)
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        model.train()
        for _ in range(12):
            optimizer.zero_grad()
            losses = []
            for frame, x, edge_index in train_frames:
                eligible = torch.tensor(frame["eligible_k1"].to_numpy() == 1)
                if not eligible.any():
                    continue
                y = torch.tensor(frame["y_k1"].fillna(0).astype(int).to_numpy(), dtype=torch.float32)
                losses.append(loss_fn(model(x, edge_index)[eligible], y[eligible]))
            if losses:
                torch.stack(losses).mean().backward()
                optimizer.step()

        model.eval()
        predictions = {}
        with torch.no_grad():
            for step, (frame, x, edge_index) in snapshot.items():
                predictions[step] = torch.sigmoid(model(x, edge_index)).numpy()
        val_rows = [(frame, predictions[step]) for step, (frame, _, _) in snapshot.items() if val_start <= step <= val_end]
        test_rows = [(frame, predictions[step]) for step, (frame, _, _) in snapshot.items() if test_start <= step <= test_end]
        val_y = np.concatenate([f.loc[f.eligible_k1 == 1, "y_k1"].astype(int).to_numpy() for f, _ in val_rows]) if val_rows else np.array([], dtype=int)
        val_p = np.concatenate([p[f.eligible_k1.to_numpy() == 1] for f, p in val_rows]) if val_rows else np.array([], dtype=float)
        thresholds = sorted(set(float(x) for x in val_p), reverse=True)
        threshold = max(thresholds, key=lambda t: f1_score(val_y, (val_p >= t).astype(int), zero_division=0)) if len(val_y) and thresholds else .5
        test_y = np.concatenate([f.loc[f.eligible_k1 == 1, "y_k1"].astype(int).to_numpy() for f, _ in test_rows]) if test_rows else np.array([], dtype=int)
        test_p = np.concatenate([p[f.eligible_k1.to_numpy() == 1] for f, p in test_rows]) if test_rows else np.array([], dtype=float)
        results.append({"fold": fold_id, "train_window": [1, train_end], "validation_window": [val_start, val_end], "test_window": [test_start, test_end], "train_rows": train_eligible, "train_positives": train_positive, "threshold": threshold, "validation": metrics(val_y, val_p, threshold), "test": metrics(test_y, test_p, threshold)})

    output = {"model": "one_layer_mean_graphsage", "horizon": 1, "features": FEATURES, "folds": results, "mean_test_average_precision": float(np.mean([r["test"]["average_precision"] for r in results if r["test"]["average_precision"] is not None])), "std_test_average_precision": float(np.std([r["test"]["average_precision"] for r in results if r["test"]["average_precision"] is not None])), "note": "Controlled ablation; same-timestep address neighborhoods only; no future edges or labels used as inputs."}
    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
