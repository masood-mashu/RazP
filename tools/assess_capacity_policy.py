"""Evaluate alert load and indicative recall under capacity-aware policies."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
from xgboost import XGBClassifier

def main():
    p=argparse.ArgumentParser(); p.add_argument('--proxy-file',type=Path,required=True); p.add_argument('--model-file',type=Path,required=True); p.add_argument('--metadata-file',type=Path,required=True); p.add_argument('--out-file',type=Path,required=True); a=p.parse_args()
    d=pd.read_csv(a.proxy_file); meta=json.loads(a.metadata_file.read_text(encoding='utf-8')); model=XGBClassifier(); model.load_model(a.model_file); d['score']=model.predict_proba(d[meta['features']])[:,1]
    results=[]
    for capacity in (10,25,50,100):
        selected=d.sort_values(['proxy_batch','score'],ascending=[True,False]).groupby('proxy_batch',sort=False).head(capacity); positives=int(d.y_k1.sum()); captured=int(selected.y_k1.sum()); results.append({'capacity_per_batch':capacity,'batches':int(d.proxy_batch.nunique()),'alerts':len(selected),'alert_rate':float(len(selected)/len(d)),'known_positive_rows':positives,'captured_known_positive_rows':captured,'indicative_recall':float(captured/positives) if positives else 0.0})
    out={'protocol':'synthetic distribution-preserving proxy capacity assessment','proxy_rows':len(d),'proxy_batches':int(d.proxy_batch.nunique()),'source':'audited Elliptic++ eligible temporal rows sampled with replacement','results':results,'safety':{'actions_triggered':0,'automatic_blocks':0},'interpretation':'Proxy-only operational evidence. It is useful for queue-load testing, not for claims about Razorpay performance or final threshold calibration.'}
    a.out_file.parent.mkdir(parents=True,exist_ok=True); a.out_file.write_text(json.dumps(out,indent=2),encoding='utf-8'); print(json.dumps(out,indent=2))
if __name__=='__main__': main()
