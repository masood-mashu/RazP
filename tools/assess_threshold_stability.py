"""Assess operational threshold stability across rolling validation folds."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev


def main():
    p = argparse.ArgumentParser(); p.add_argument('--evaluation-file', type=Path, required=True); p.add_argument('--out-file', type=Path, required=True); a = p.parse_args()
    raw = json.loads(a.evaluation_file.read_text(encoding='utf-8'))
    folds = raw['results']['1']['folds']
    rows = []
    for f in folds:
        v = f['validation']; predicted = (v['recall'] * v['positives'] / v['precision']) if v['precision'] else 0; rows.append({'fold': f['fold'], 'validation_window': f['validation_window'], 'rows': v['rows'], 'positives': v['positives'], 'threshold': f['threshold'], 'alerts_at_threshold': round(predicted), 'precision': v['precision'], 'recall': v['recall'], 'f1': v['f1']})
    thresholds = [x['threshold'] for x in rows]
    result = {'protocol':'rolling-origin validation threshold stability','horizon':1,'folds':len(rows),'total_validation_rows':sum(x['rows'] for x in rows),'total_validation_positives':sum(x['positives'] for x in rows),'threshold_summary':{'mean':mean(thresholds),'std':pstdev(thresholds),'min':min(thresholds),'max':max(thresholds),'coefficient_of_variation':pstdev(thresholds)/mean(thresholds)},'operational_gate':{'status':'research_only','reason':'Thresholds vary materially across folds and validation positives remain sparse; collect a larger production-like validation stream before deployment.','required_before_deployment':['recalibrate on representative traffic','monitor alert-rate and recall by time window','freeze threshold only after drift review','keep automatic blocks disabled']},'folds':rows,'source':str(a.evaluation_file)}
    a.out_file.parent.mkdir(parents=True, exist_ok=True); a.out_file.write_text(json.dumps(result, indent=2), encoding='utf-8'); print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
