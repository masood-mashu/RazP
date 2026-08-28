"""Build a seeded, distribution-preserving validation proxy for capacity testing."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

def main():
    p=argparse.ArgumentParser(); p.add_argument('--base-file',type=Path,required=True); p.add_argument('--graph-file',type=Path,required=True); p.add_argument('--split-file',type=Path,required=True); p.add_argument('--out-file',type=Path,required=True); p.add_argument('--rows',type=int,default=20000); a=p.parse_args()
    base=pd.read_csv(a.base_file); graph=pd.read_csv(a.graph_file); split=pd.read_csv(a.split_file)
    d=split.merge(base.merge(graph,on=['address','time_step'],validate='one_to_one'),on=['address','time_step'],validate='one_to_one'); d=d[d.eligible_k1==1].copy()
    proxy=d.sample(n=a.rows,replace=True,random_state=42).reset_index(drop=True); proxy.insert(0,'proxy_row_id',[f'proxy-{i:06d}' for i in range(len(proxy))]); proxy.insert(1,'proxy_batch',(proxy.index//500)+1); proxy['source_row_id']=proxy['address'].astype(str)+'@'+proxy['time_step'].astype(str)
    a.out_file.parent.mkdir(parents=True,exist_ok=True); proxy.to_csv(a.out_file,index=False); print({'rows':len(proxy),'batches':int(proxy.proxy_batch.max()),'source_rows':len(d),'positive_rate':float(proxy.y_k1.mean())})
if __name__=='__main__': main()
