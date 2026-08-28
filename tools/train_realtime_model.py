"""Train and save the selected horizon-1 detector for API inference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import f1_score
from xgboost import XGBClassifier

FEATURES = ["in_tx_count_t","out_tx_count_t","tx_count_t","in_tx_count_last3","out_tx_count_last3","tx_count_last3","in_tx_count_last5","out_tx_count_last5","tx_count_last5","cumulative_in_tx_count","cumulative_out_tx_count","cumulative_tx_count","active_timesteps_to_t","active_last3_timesteps","active_last5_timesteps","in_degree_t","out_degree_t","unique_counterparties_t","unique_counterparties_last3","unique_counterparties_last5","new_counterparties_t","cumulative_unique_counterparties"]

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base-file', type=Path, required=True)
    p.add_argument('--graph-file', type=Path, required=True)
    p.add_argument('--split-file', type=Path, required=True)
    p.add_argument('--model-file', type=Path, required=True)
    p.add_argument('--metadata-file', type=Path, required=True)
    a = p.parse_args()
    base = pd.read_csv(a.base_file)
    graph = pd.read_csv(a.graph_file)
    split = pd.read_csv(a.split_file)
    data = split.merge(base.merge(graph, on=['address','time_step'], validate='one_to_one'), on=['address','time_step'], validate='one_to_one')
    d = data[data.eligible_k1 == 1]
    train, val = d[d.split == 'train'], d[d.split == 'validation']
    pos = int(train.y_k1.sum())
    model = XGBClassifier(n_estimators=250, max_depth=4, learning_rate=.05, min_child_weight=3, subsample=.85, colsample_bytree=.9, reg_lambda=2.0, objective='binary:logistic', eval_metric='aucpr', tree_method='hist', scale_pos_weight=(len(train)-pos)/pos, random_state=42, n_jobs=4)
    model.fit(train[FEATURES], train.y_k1.astype(int))
    val_score = model.predict_proba(val[FEATURES])[:, 1]
    threshold = max((float(x) for x in val_score), key=lambda t: f1_score(val.y_k1.astype(int), (val_score >= t).astype(int), zero_division=0))
    a.model_file.parent.mkdir(parents=True, exist_ok=True)
    a.metadata_file.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(a.model_file)
    a.metadata_file.write_text(json.dumps({'model_version':'xgb-graph-v1','horizon':1,'features':FEATURES,'threshold':threshold,'training_rows':len(train),'validation_rows':len(val)}, indent=2), encoding='utf-8')
    print(json.dumps({'model_file':str(a.model_file),'threshold':threshold}, indent=2))

if __name__ == '__main__':
    main()
