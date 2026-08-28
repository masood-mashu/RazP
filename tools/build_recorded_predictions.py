"""Create a reproducible actor-level prediction snapshot for the demo."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import f1_score
from xgboost import XGBClassifier

FEATURES = ["in_tx_count_t","out_tx_count_t","tx_count_t","in_tx_count_last3","out_tx_count_last3","tx_count_last3","in_tx_count_last5","out_tx_count_last5","tx_count_last5","cumulative_in_tx_count","cumulative_out_tx_count","cumulative_tx_count","active_timesteps_to_t","active_last3_timesteps","active_last5_timesteps","in_degree_t","out_degree_t","unique_counterparties_t","unique_counterparties_last3","unique_counterparties_last5","new_counterparties_t","cumulative_unique_counterparties"]

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-file", type=Path, required=True)
    ap.add_argument("--graph-file", type=Path, required=True)
    ap.add_argument("--split-file", type=Path, required=True)
    ap.add_argument("--out-file", type=Path, required=True)
    args = ap.parse_args()
    base = pd.read_csv(args.base_file)
    graph = pd.read_csv(args.graph_file)
    split = pd.read_csv(args.split_file)
    data = split.merge(base.merge(graph, on=["address", "time_step"], validate="one_to_one"), on=["address", "time_step"], validate="one_to_one")
    d = data[data.eligible_k1 == 1].copy()
    train, val, test = [d[d.split == s].copy() for s in ("train", "validation", "test")]
    positives = int(train.y_k1.sum())
    model = XGBClassifier(n_estimators=250, max_depth=4, learning_rate=.05, min_child_weight=3, subsample=.85, colsample_bytree=.9, reg_lambda=2.0, objective="binary:logistic", eval_metric="aucpr", tree_method="hist", scale_pos_weight=(len(train)-positives)/positives, random_state=42, n_jobs=4)
    model.fit(train[FEATURES], train.y_k1.astype(int))
    val_score = model.predict_proba(val[FEATURES])[:, 1]
    threshold = max((float(x) for x in val_score), key=lambda t: f1_score(val.y_k1.astype(int), (val_score >= t).astype(int), zero_division=0))
    test["score"] = model.predict_proba(test[FEATURES])[:, 1]
    test["band"] = test.score.map(lambda x: "critical" if x >= max(.85, threshold) else "high" if x >= threshold else "monitor")
    test["action"] = test.band.map(lambda x: "Monitor" if x == "monitor" else "Human review")
    test["evidence"] = test.apply(lambda r: "; ".join([f"tx activity {int(r.tx_count_t)}", f"counterparties {int(r.unique_counterparties_t)}", f"new links {int(r.new_counterparties_t)}"]), axis=1)
    rows = test.sort_values("score", ascending=False).head(50)
    alerts = [{"id": f"ACT-{i:04d}", "address": r.address, "time_step": int(r.time_step), "time": f"timestep {int(r.time_step)}", "score": round(float(r.score), 6), "band": r.band, "action": r.action, "title": "High-risk actor signal" if r.band == "critical" else "Emerging activity pattern" if r.band == "high" else "Low-confidence signal", "detail": "Recorded model output from the temporal continuation test window.", "evidence": r.evidence.split("; "), "model_version": "xgb-graph-v1", "source": "temporal_continuation_rows.csv"} for i, (_, r) in enumerate(rows.iterrows(), 1)]
    result = {"schema_version":"risk-ops-predictions.v1","generated_at":"2026-08-28","mode":"recorded","model":{"name":"Graph-enhanced XGBoost","version":"xgb-graph-v1","horizon":1,"primary":True},"threshold":float(threshold),"source":{"split_file":str(args.split_file),"test_rows":int(len(test)),"returned_alerts":len(alerts)},"measured":{"rolling_mean_ap":0.0677306990,"rolling_std_ap":0.0793144952,"gnn_ablation_ap":0.0650,"horizons":[{"k":1,"ap":0.0677306990},{"k":3,"ap":0.0303233806},{"k":5,"ap":0.0235581979}],"references":{"causal_xgb_k1_ap":0.0202167,"rules_k1_ap":0.0071421}},"policy":{"automatic_blocks":0},"alerts":alerts}
    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"threshold":threshold,"test_rows":len(test),"alerts":len(alerts)}, indent=2))

if __name__ == "__main__":
    main()
