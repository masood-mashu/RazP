"""Render saved precision-recall points as a dependency-free SVG."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def main():
    p=argparse.ArgumentParser(); p.add_argument('--metrics',type=Path,required=True); p.add_argument('--out',type=Path,required=True); a=p.parse_args(); j=json.loads(a.metrics.read_text(encoding='utf-8')); c=j['primary_test']['precision_recall_curve']; pts=[]
    for r,pr in zip(c['recall'],c['precision']): pts.append(f'{60+r*500:.1f},{40+(1-pr)*300:.1f}')
    base=j['primary_test']['positive_rate']; svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420"><rect width="100%" height="100%" fill="#ffffff"/><text x="60" y="24" font-family="Arial" font-size="18" fill="#152238">Horizon-1 precision–recall curve</text><line x1="60" y1="40" x2="60" y2="340" stroke="#9aa6b8"/><line x1="60" y1="340" x2="560" y2="340" stroke="#9aa6b8"/><line x1="60" y1="{40+(1-base)*300:.1f}" x2="560" y2="{40+(1-base)*300:.1f}" stroke="#9aa6b8" stroke-dasharray="6 5"/><polyline fill="none" stroke="#2364e8" stroke-width="3" points="{' '.join(pts)}"/><text x="270" y="382" font-family="Arial" font-size="13">Recall</text><text x="16" y="210" transform="rotate(-90 16 210)" font-family="Arial" font-size="13">Precision</text><text x="390" y="{35+(1-base)*300:.1f}" font-family="Arial" font-size="11" fill="#6b7890">Random baseline: {base:.4f}</text></svg>'''
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(svg,encoding='utf-8')
if __name__=='__main__': main()
