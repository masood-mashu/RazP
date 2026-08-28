"""Error analysis for the temporal-continuation XGBoost baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss
from xgboost import XGBClassifier


FEATURES = [
    "in_tx_count_t", "out_tx_count_t", "tx_count_t", "in_tx_count_last3", "out_tx_count_last3", "tx_count_last3",
    "in_tx_count_last5", "out_tx_count_last5", "tx_count_last5", "cumulative_in_tx_count", "cumulative_out_tx_count",
    "cumulative_tx_count", "active_timesteps_to_t", "active_last3_timesteps", "active_last5_timesteps",
]


def top_k(y, score, ks=(10, 25, 50, 100, 250)):
    order = score.argsort()[::-1]
    result = {}
    for k in ks:
        chosen = y.iloc[order[: min(k, len(y))]]
        result[str(k)] = {"alerts": int(len(chosen)), "true_positives": int(chosen.sum()), "precision": float(chosen.mean()) if len(chosen) else 0.0, "recall": float(chosen.sum() / y.sum()) if y.sum() else None}
    return result


def calibration(y, score):
    bins = []
    for low, high in [(0.0, .01), (.01, .05), (.05, .2), (.2, .5), (.5, 1.01)]:
        mask = (score >= low) & (score < high)
        if mask.any():
            bins.append({"range": f"[{low},{high})", "n": int(mask.sum()), "mean_score": float(score[mask].mean()), "observed_rate": float(y[mask].mean())})
    return bins


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature-file", type=Path, required=True)
    parser.add_argument("--split-file", type=Path, required=True)
    parser.add_argument("--out-file", type=Path, required=True)
    args = parser.parse_args()

    features = pd.read_csv(args.feature_file, usecols=["address", "time_step"] + FEATURES)
    split = pd.read_csv(args.split_file)
    data = split.merge(features, on=["address", "time_step"], how="inner", validate="one_to_one")
    result = {}
    for k in (1, 3, 5):
        eligible = data[data[f"eligible_k{k}"] == 1]
        train = eligible[eligible.split == "train"]
        validation = eligible[eligible.split == "validation"]
        test = eligible[eligible.split == "test"].copy()
        y_train = train[f"y_k{k}"].astype(int)
        pos = int(y_train.sum())
        model = XGBClassifier(n_estimators=250, max_depth=4, learning_rate=.05, min_child_weight=3, subsample=.85, colsample_bytree=.9, reg_lambda=2.0, objective="binary:logistic", eval_metric="aucpr", tree_method="hist", scale_pos_weight=(len(y_train) - pos) / pos, random_state=42, n_jobs=4)
        model.fit(train[FEATURES], y_train)
        val_score = model.predict_proba(validation[FEATURES])[:, 1]
        candidates = sorted(set(float(x) for x in val_score), reverse=True)
        threshold = max(candidates, key=lambda t: ((validation[f"y_k{k}"].astype(int).to_numpy() == 1) & (val_score >= t)).sum() / max(1, ((val_score >= t).sum()))) if candidates else .5
        y_test = test[f"y_k{k}"].astype(int)
        score = model.predict_proba(test[FEATURES])[:, 1]
        y_array = y_test.to_numpy()
        result[str(k)] = {
            "test_rows": int(len(test)),
            "test_positives": int(y_array.sum()),
            "positive_rate": float(y_array.mean()),
            "average_precision": float(average_precision_score(y_array, score)),
            "brier_score": float(brier_score_loss(y_array, score)),
            "validation_threshold_precision_oriented": float(threshold),
            "top_k": top_k(y_test.reset_index(drop=True), score),
            "calibration": calibration(y_array, score),
            "score_mean_positive": float(score[y_array == 1].mean()) if y_array.sum() else None,
            "score_mean_negative": float(score[y_array == 0].mean()) if (y_array == 0).sum() else None,
            "feature_importance_gain": {name: float(value) for name, value in sorted(zip(FEATURES, model.feature_importances_), key=lambda pair: -pair[1])},
            "positive_counts_by_test_timestep": {str(step): int(group[f"y_k{k}"].sum()) for step, group in test.groupby("time_step")},
        }
    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
