"""Build base-rate, lift, top-K, and precision-recall artifacts."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve
from xgboost import XGBClassifier

FEATURES=["in_tx_count_t","out_tx_count_t","tx_count_t","in_tx_count_last3","out_tx_count_last3","tx_count_last3","in_tx_count_last5","out_tx_count_last5","tx_count_last5","cumulative_in_tx_count","cumulative_out_tx_count","cumulative_tx_count","active_timesteps_to_t","active_last3_timesteps","active_last5_timesteps","in_degree_t","out_degree_t","unique_counterparties_t","unique_counterparties_last3","unique_counterparties_last5","new_counterparties_t","cumulative_unique_counterparties"]

def main():
    p=argparse.ArgumentParser(); p.add_argument('--evaluation-file',type=Path,required=True); p.add_argument('--base-file',type=Path,required=True); p.add_argument('--graph-file',type=Path,required=True); p.add_argument('--split-file',type=Path,required=True); p.add_argument('--out-json',type=Path,required=True); p.add_argument('--out-plot',type=Path,required=True); a=p.parse_args()
    evaluation=json.loads(a.evaluation_file.read_text(encoding='utf-8'))
    summary={}
    for k in ('1','3','5'):
        folds=evaluation['results'][k]['folds']; test_rows=sum(f['test']['rows'] for f in folds if not f.get('skipped')); positives=sum(f['test']['positives'] for f in folds if not f.get('skipped')); base=positives/test_rows
        summary[k]={'rolling_mean_ap':evaluation['results'][k]['test_average_precision_mean'],'rolling_std_ap':evaluation['results'][k]['test_average_precision_std'],'pooled_test_rows':test_rows,'pooled_test_positives':positives,'pooled_test_positive_rate':base,'ap_lift_over_random':evaluation['results'][k]['test_average_precision_mean']/base if base else None}
    base=pd.read_csv(a.base_file); graph=pd.read_csv(a.graph_file); split=pd.read_csv(a.split_file); d=split.merge(base.merge(graph,on=['address','time_step'],validate='one_to_one'),on=['address','time_step'],validate='one_to_one'); d=d[d.eligible_k1==1]; train=d[d.split=='train']; val=d[d.split=='validation']; test=d[d.split=='test']; pos=int(train.y_k1.sum())
    model=XGBClassifier(n_estimators=250,max_depth=4,learning_rate=.05,min_child_weight=3,subsample=.85,colsample_bytree=.9,reg_lambda=2.0,objective='binary:logistic',eval_metric='aucpr',tree_method='hist',scale_pos_weight=(len(train)-pos)/pos,random_state=42,n_jobs=4); model.fit(train[FEATURES],train.y_k1.astype(int)); val_score=model.predict_proba(val[FEATURES])[:,1]; threshold=max((float(x) for x in val_score),key=lambda t: __import__('sklearn').metrics.f1_score(val.y_k1.astype(int),(val_score>=t).astype(int),zero_division=0)); test_score=model.predict_proba(test[FEATURES])[:,1]; y=test.y_k1.astype(int).to_numpy(); order=test_score.argsort()[::-1]; topk={}
    for k in (10,25,50,100):
        selected=order[:min(k,len(order))]; topk[str(k)]={'precision_at_k':float(y[selected].mean()),'recall_at_k':float(y[selected].sum()/max(y.sum(),1)),'positive_hits':int(y[selected].sum()),'capacity':k}
    precision,recall,_=precision_recall_curve(y,test_score); result={'base_rates_and_lift':summary,'primary_test':{'rows':len(test),'positives':int(y.sum()),'positive_rate':float(y.mean()),'average_precision':float(average_precision_score(y,test_score)),'validation_threshold':float(threshold),'top_k':topk,'precision_recall_curve':{'precision':precision.tolist(),'recall':recall.tolist()},'note':'Threshold was selected on validation data; test data is used only for final reporting.'}}
    a.out_json.parent.mkdir(parents=True,exist_ok=True); a.out_plot.parent.mkdir(parents=True,exist_ok=True); a.out_json.write_text(json.dumps(result,indent=2),encoding='utf-8')
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(7,5)); plt.step(recall,precision,where='post',label=f"Graph XGBoost (AP={result['primary_test']['average_precision']:.4f})"); plt.axhline(y.mean(),color='#9aa6b8',linestyle='--',label=f"Random baseline ({y.mean():.4f})"); plt.xlabel('Recall'); plt.ylabel('Precision'); plt.title('Horizon-1 precision–recall curve'); plt.legend(); plt.grid(alpha=.2); plt.tight_layout(); plt.savefig(a.out_plot,dpi=160); plt.close()
    except ImportError: result['plot_note']='matplotlib unavailable; curve data remains in the JSON artifact.'
    print(json.dumps({'k1_base_rate':summary['1']['pooled_test_positive_rate'],'k1_lift':summary['1']['ap_lift_over_random'],'top50_precision':topk['50']['precision_at_k'],'top50_recall':topk['50']['recall_at_k'],'plot':str(a.out_plot)},indent=2))
if __name__=='__main__': main()
