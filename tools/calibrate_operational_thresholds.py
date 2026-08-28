"""Calibrate review thresholds on validation data only; never use the test set."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score
from xgboost import XGBClassifier

FEATURES = ["in_tx_count_t","out_tx_count_t","tx_count_t","in_tx_count_last3","out_tx_count_last3","tx_count_last3","in_tx_count_last5","out_tx_count_last5","tx_count_last5","cumulative_in_tx_count","cumulative_out_tx_count","cumulative_tx_count","active_timesteps_to_t","active_last3_timesteps","active_last5_timesteps","in_degree_t","out_degree_t","unique_counterparties_t","unique_counterparties_last3","unique_counterparties_last5","new_counterparties_t","cumulative_unique_counterparties"]

def main():
    p=argparse.ArgumentParser(); p.add_argument('--base-file',type=Path,required=True); p.add_argument('--graph-file',type=Path,required=True); p.add_argument('--split-file',type=Path,required=True); p.add_argument('--out-file',type=Path,required=True); a=p.parse_args()
    base=pd.read_csv(a.base_file); graph=pd.read_csv(a.graph_file); split=pd.read_csv(a.split_file)
    d=split.merge(base.merge(graph,on=['address','time_step'],validate='one_to_one'),on=['address','time_step'],validate='one_to_one'); d=d[d.eligible_k1==1]
    train=d[d.split=='train']; val=d[d.split=='validation']; pos=int(train.y_k1.sum())
    model=XGBClassifier(n_estimators=250,max_depth=4,learning_rate=.05,min_child_weight=3,subsample=.85,colsample_bytree=.9,reg_lambda=2.0,objective='binary:logistic',eval_metric='aucpr',tree_method='hist',scale_pos_weight=(len(train)-pos)/pos,random_state=42,n_jobs=4)
    model.fit(train[FEATURES],train.y_k1.astype(int)); y=val.y_k1.astype(int).to_numpy(); scores=model.predict_proba(val[FEATURES])[:,1]
    candidates=sorted(set([.25,.40,.50,.571304976940155,.65,.75,.85]))
    rows=[]
    for threshold in candidates:
        pred=(scores>=threshold).astype(int); rows.append({'threshold':threshold,'alerts':int(pred.sum()),'alert_rate':float(pred.mean()),'precision':float(precision_score(y,pred,zero_division=0)),'recall':float(recall_score(y,pred,zero_division=0)),'f1':float(f1_score(y,pred,zero_division=0))})
    chosen=max(rows,key=lambda r:r['f1'])
    result={'protocol':'validation-only calibration','horizon':1,'validation_rows':len(val),'validation_positives':int(y.sum()),'chosen_threshold':chosen['threshold'],'policy':{'critical_score':.85,'high_score':chosen['threshold'],'monitor_score':0.0,'automatic_blocks':0},'candidates':rows,'note':'The held-out test window was not used for threshold selection.'}
    a.out_file.parent.mkdir(parents=True,exist_ok=True); a.out_file.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result,indent=2))

if __name__=='__main__': main()
