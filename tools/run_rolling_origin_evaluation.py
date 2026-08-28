"""Evaluate the causal graph baseline across multiple chronological folds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from xgboost import XGBClassifier


BASE = ["in_tx_count_t", "out_tx_count_t", "tx_count_t", "in_tx_count_last3", "out_tx_count_last3", "tx_count_last3", "in_tx_count_last5", "out_tx_count_last5", "tx_count_last5", "cumulative_in_tx_count", "cumulative_out_tx_count", "cumulative_tx_count", "active_timesteps_to_t", "active_last3_timesteps", "active_last5_timesteps"]
GRAPH = ["in_degree_t", "out_degree_t", "unique_counterparties_t", "unique_counterparties_last3", "unique_counterparties_last5", "new_counterparties_t", "cumulative_unique_counterparties"]
FEATURES = BASE + GRAPH
FOLDS = [(20, 21, 25, 26, 30), (25, 26, 30, 31, 35), (30, 31, 35, 36, 40), (35, 36, 40, 41, 45), (39, 40, 44, 45, 49)]


def score(y, p, threshold):
    pred = (p >= threshold).astype(int)
    return {"rows": int(len(y)), "positives": int(y.sum()), "positive_rate": float(y.mean()) if len(y) else None, "average_precision": float(average_precision_score(y, p)) if y.sum() else None, "precision": float(precision_score(y, pred, zero_division=0)), "recall": float(recall_score(y, pred, zero_division=0)), "f1": float(f1_score(y, pred, zero_division=0))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-file", type=Path, required=True)
    parser.add_argument("--graph-file", type=Path, required=True)
    parser.add_argument("--label-file", type=Path, required=True)
    parser.add_argument("--out-file", type=Path, required=True)
    args = parser.parse_args()
    base = pd.read_csv(args.base_file)
    graph = pd.read_csv(args.graph_file)
    labels = pd.read_csv(args.label_file)
    data = labels.merge(base.merge(graph, on=["address", "time_step"], how="inner", validate="one_to_one"), on=["address", "time_step"], how="inner", validate="one_to_one")
    results = {}
    for k in (1, 3, 5):
        folds = []
        for index, (train_end, val_start, val_end, test_start, test_end) in enumerate(FOLDS, 1):
            eligible = data[data[f"eligible_k{k}"] == 1]
            train = eligible[eligible.time_step <= train_end]
            val = eligible[(eligible.time_step >= val_start) & (eligible.time_step <= val_end)]
            test = eligible[(eligible.time_step >= test_start) & (eligible.time_step <= test_end)]
            if len(train) == 0 or len(val) == 0 or len(test) == 0 or train[f"y_k{k}"].sum() == 0:
                folds.append({"fold": index, "skipped": True, "train_rows": int(len(train)), "validation_rows": int(len(val)), "test_rows": int(len(test))})
                continue
            y_train = train[f"y_k{k}"].astype(int)
            positives = int(y_train.sum())
            model = XGBClassifier(n_estimators=250, max_depth=4, learning_rate=.05, min_child_weight=3, subsample=.85, colsample_bytree=.9, reg_lambda=2.0, objective="binary:logistic", eval_metric="aucpr", tree_method="hist", scale_pos_weight=(len(y_train) - positives) / positives, random_state=42, n_jobs=4)
            model.fit(train[FEATURES], y_train)
            val_y = val[f"y_k{k}"].astype(int).to_numpy()
            val_p = model.predict_proba(val[FEATURES])[:, 1]
            thresholds = sorted(set(float(x) for x in val_p), reverse=True)
            threshold = max(thresholds, key=lambda t: f1_score(val_y, (val_p >= t).astype(int), zero_division=0)) if thresholds else .5
            test_y = test[f"y_k{k}"].astype(int).to_numpy()
            test_p = model.predict_proba(test[FEATURES])[:, 1]
            folds.append({"fold": index, "train_window": [1, train_end], "validation_window": [val_start, val_end], "test_window": [test_start, test_end], "threshold": threshold, "train": score(y_train.to_numpy(), model.predict_proba(train[FEATURES])[:, 1], threshold), "validation": score(val_y, val_p, threshold), "test": score(test_y, test_p, threshold)})
        valid = [fold for fold in folds if not fold.get("skipped") and fold["test"]["average_precision"] is not None]
        test_ap = [fold["test"]["average_precision"] for fold in valid]
        results[str(k)] = {"folds": folds, "test_average_precision_mean": float(np.mean(test_ap)) if test_ap else None, "test_average_precision_std": float(np.std(test_ap)) if test_ap else None, "valid_folds": len(valid)}
    result = {"fold_definition": FOLDS, "features": FEATURES, "results": results, "recommendation": "Use rolling-origin stability as a gate; do not claim a temporal GNN improvement from a single split."}
    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
