"""Run no-action shadow scoring over the full available temporal stream."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from xgboost import XGBClassifier

FEATURES = ["in_tx_count_t","out_tx_count_t","tx_count_t","in_tx_count_last3","out_tx_count_last3","tx_count_last3","in_tx_count_last5","out_tx_count_last5","tx_count_last5","cumulative_in_tx_count","cumulative_out_tx_count","cumulative_tx_count","active_timesteps_to_t","active_last3_timesteps","active_last5_timesteps","in_degree_t","out_degree_t","unique_counterparties_t","unique_counterparties_last3","unique_counterparties_last5","new_counterparties_t","cumulative_unique_counterparties"]

def main():
    p=argparse.ArgumentParser(); p.add_argument('--base-file',type=Path,required=True); p.add_argument('--graph-file',type=Path,required=True); p.add_argument('--split-file',type=Path,required=True); p.add_argument('--model-file',type=Path,required=True); p.add_argument('--metadata-file',type=Path,required=True); p.add_argument('--out-file',type=Path,required=True); a=p.parse_args()
    base=pd.read_csv(a.base_file); graph=pd.read_csv(a.graph_file); split=pd.read_csv(a.split_file)
    d=split.merge(base.merge(graph,on=['address','time_step'],validate='one_to_one'),on=['address','time_step'],validate='one_to_one'); d=d[d.eligible_k1==1].copy()
    meta=json.loads(a.metadata_file.read_text(encoding='utf-8')); model=XGBClassifier(); model.load_model(a.model_file)
    d['score']=model.predict_proba(d[meta['features']])[:,1]; threshold=float(meta['threshold']); d['band']=d.score.map(lambda x:'critical' if x>=max(.85,threshold) else 'high' if x>=threshold else 'monitor')
    by_time=[]
    for t,g in d.groupby('time_step'):
        by_time.append({'time_step':int(t),'rows':len(g),'mean_score':float(g.score.mean()),'p95_score':float(g.score.quantile(.95)),'high_or_critical':int((g.score>=threshold).sum()),'critical':int((g.score>=max(.85,threshold)).sum())})
    result={'mode':'shadow_no_action','model_version':meta['model_version'],'threshold':threshold,'rows_scored':len(d),'timesteps':len(by_time),'score_summary':{'mean':float(d.score.mean()),'p95':float(d.score.quantile(.95)),'max':float(d.score.max())},'band_counts':{k:int(v) for k,v in d.band.value_counts().to_dict().items()},'timestep_summary':by_time,'safety':{'actions_triggered':0,'automatic_blocks':0,'customer_impact':False},'interpretation':'Distribution and drift telemetry only; this stream is not a representative Razorpay validation set and must not be used as deployment evidence.'}
    a.out_file.parent.mkdir(parents=True,exist_ok=True); a.out_file.write_text(json.dumps(result,indent=2),encoding='utf-8'); print(json.dumps(result,indent=2))

if __name__=='__main__': main()
