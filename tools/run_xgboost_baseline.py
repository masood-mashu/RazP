"""Train XGBoost baselines on the causal actor-time features."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from xgboost import XGBClassifier


FEATURES = [
    "in_tx_count_t", "out_tx_count_t", "tx_count_t",
    "in_tx_count_last3", "out_tx_count_last3", "tx_count_last3",
    "in_tx_count_last5", "out_tx_count_last5", "tx_count_last5",
    "cumulative_in_tx_count", "cumulative_out_tx_count", "cumulative_tx_count",
    "active_timesteps_to_t", "active_last3_timesteps", "active_last5_timesteps",
]


def evaluate(y, score, threshold):
    pred = (score >= threshold).astype(int)
    return {
        "n": int(len(y)),
        "positives": int(y.sum()),
        "pr_auc": float(average_precision_score(y, score)) if y.sum() else None,
        "threshold": float(threshold),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "tp": int(((pred == 1) & (y == 1)).sum()),
        "fp": int(((pred == 1) & (y == 0)).sum()),
        "fn": int(((pred == 0) & (y == 1)).sum()),
    }


def choose_threshold(y, score):
    candidates = sorted(set(float(x) for x in score), reverse=True)
    best_threshold, best_f1 = 0.5, -1.0
    for threshold in candidates:
        f1 = f1_score(y, (score >= threshold).astype(int), zero_division=0)
        if f1 > best_f1:
            best_f1, best_threshold = f1, threshold
    return best_threshold


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature-file", type=Path, required=True)
    parser.add_argument("--split-files", nargs=2, required=True)
    parser.add_argument("--out-file", type=Path, required=True)
    args = parser.parse_args()

    feature_df = pd.read_csv(args.feature_file, usecols=["address", "time_step"] + FEATURES)
    outputs = {}
    for split_file in args.split_files:
        split_name = Path(split_file).stem
        split_df = pd.read_csv(split_file)
        data = split_df.merge(feature_df, on=["address", "time_step"], how="inner", validate="one_to_one")
        split_results = {}
        for k in (1, 3, 5):
            data_k = data[data[f"eligible_k{k}"] == 1].copy()
            train = data_k[data_k["split"] == "train"]
            validation = data_k[data_k["split"] == "validation"]
            test = data_k[data_k["split"] == "test"]
            X_train, y_train = train[FEATURES], train[f"y_k{k}"].astype(int)
            positive = int(y_train.sum())
            negative = int(len(y_train) - positive)
            model = XGBClassifier(
                n_estimators=250,
                max_depth=4,
                learning_rate=0.05,
                min_child_weight=3,
                subsample=0.85,
                colsample_bytree=0.9,
                reg_lambda=2.0,
                objective="binary:logistic",
                eval_metric="aucpr",
                tree_method="hist",
                scale_pos_weight=(negative / positive if positive else 1.0),
                random_state=42,
                n_jobs=4,
            )
            model.fit(X_train, y_train)
            validation_score = model.predict_proba(validation[FEATURES])[:, 1]
            threshold = choose_threshold(validation[f"y_k{k}"].astype(int).to_numpy(), validation_score)
            split_results[str(k)] = {
                "train": evaluate(y_train.to_numpy(), model.predict_proba(X_train)[:, 1], threshold),
                "validation": evaluate(validation[f"y_k{k}"].astype(int).to_numpy(), validation_score, threshold),
                "test": evaluate(test[f"y_k{k}"].astype(int).to_numpy(), model.predict_proba(test[FEATURES])[:, 1], threshold),
                "training_rows": int(len(train)),
                "validation_rows": int(len(validation)),
                "test_rows": int(len(test)),
            }
        outputs[split_name] = split_results

    result = {"features": FEATURES, "model": "XGBClassifier", "random_state": 42, "results": outputs}
    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
