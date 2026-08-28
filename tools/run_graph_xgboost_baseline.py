"""Evaluate XGBoost with causal activity plus graph-structural features."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from xgboost import XGBClassifier


BASE = ["in_tx_count_t", "out_tx_count_t", "tx_count_t", "in_tx_count_last3", "out_tx_count_last3", "tx_count_last3", "in_tx_count_last5", "out_tx_count_last5", "tx_count_last5", "cumulative_in_tx_count", "cumulative_out_tx_count", "cumulative_tx_count", "active_timesteps_to_t", "active_last3_timesteps", "active_last5_timesteps"]
GRAPH = ["in_degree_t", "out_degree_t", "unique_counterparties_t", "unique_counterparties_last3", "unique_counterparties_last5", "new_counterparties_t", "cumulative_unique_counterparties"]
FEATURES = BASE + GRAPH


def evaluate(y, score, threshold):
    pred = (score >= threshold).astype(int)
    return {"n": int(len(y)), "positives": int(y.sum()), "average_precision": float(average_precision_score(y, score)), "threshold": float(threshold), "precision": float(precision_score(y, pred, zero_division=0)), "recall": float(recall_score(y, pred, zero_division=0)), "f1": float(f1_score(y, pred, zero_division=0))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-file", type=Path, required=True)
    parser.add_argument("--graph-file", type=Path, required=True)
    parser.add_argument("--split-files", nargs=2, required=True)
    parser.add_argument("--out-file", type=Path, required=True)
    args = parser.parse_args()
    base = pd.read_csv(args.base_file)
    graph = pd.read_csv(args.graph_file)
    structural = base.merge(graph, on=["address", "time_step"], how="inner", validate="one_to_one")
    output = {}
    for split_file in args.split_files:
        name = Path(split_file).stem
        split = pd.read_csv(split_file)
        data = split.merge(structural, on=["address", "time_step"], how="inner", validate="one_to_one")
        output[name] = {}
        for k in (1, 3, 5):
            d = data[data[f"eligible_k{k}"] == 1]
            train, val, test = (d[d.split == s] for s in ("train", "validation", "test"))
            y_train = train[f"y_k{k}"].astype(int)
            pos = int(y_train.sum())
            model = XGBClassifier(n_estimators=250, max_depth=4, learning_rate=.05, min_child_weight=3, subsample=.85, colsample_bytree=.9, reg_lambda=2.0, objective="binary:logistic", eval_metric="aucpr", tree_method="hist", scale_pos_weight=(len(y_train) - pos) / pos, random_state=42, n_jobs=4)
            model.fit(train[FEATURES], y_train)
            val_y = val[f"y_k{k}"].astype(int).to_numpy()
            val_score = model.predict_proba(val[FEATURES])[:, 1]
            thresholds = sorted(set(float(x) for x in val_score), reverse=True)
            threshold = max(thresholds, key=lambda t: f1_score(val_y, (val_score >= t).astype(int), zero_division=0)) if thresholds else .5
            test_y = test[f"y_k{k}"].astype(int).to_numpy()
            output[name][str(k)] = {"train": evaluate(y_train.to_numpy(), model.predict_proba(train[FEATURES])[:, 1], threshold), "validation": evaluate(val_y, val_score, threshold), "test": evaluate(test_y, model.predict_proba(test[FEATURES])[:, 1], threshold), "training_rows": int(len(train)), "validation_rows": int(len(val)), "test_rows": int(len(test))}
    result = {"model": "XGBClassifier_graph_structural", "features": FEATURES, "random_state": 42, "results": output}
    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
