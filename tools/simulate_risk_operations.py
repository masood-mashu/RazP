"""Exercise the risk-operations contract with deterministic demo scenarios."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def band(score: float, critical: float = 0.80, high: float = 0.50) -> str:
    if score >= critical:
        return "critical"
    if score >= high:
        return "high"
    return "monitor"


def process(events, model_available=True, max_alerts=50):
    audit = []
    if not model_available:
        return {"mode": "rules_only_monitor", "automatic_blocks": 0, "alerts": [], "audit": ["model_unavailable_fallback"]}
    unique = {}
    for event in events:
        key = (event["address"], event["time_step"], event["model_version"])
        if key in unique:
            audit.append(f"duplicate_suppressed:{key[0]}:{key[1]}")
            continue
        if event.get("missing_features"):
            event = {**event, "band": "insufficient_evidence", "action": "human_review"}
        else:
            event = {**event, "band": band(event["score"]), "action": "human_review" if event["score"] >= .5 else "monitor"}
        unique[key] = event
    ranked = sorted(unique.values(), key=lambda item: item.get("score", 0), reverse=True)
    alerts = ranked[:max_alerts]
    for deferred in ranked[max_alerts:]:
        audit.append(f"deferred_capacity:{deferred['address']}:{deferred['time_step']}")
    return {"mode": "model", "automatic_blocks": 0, "alerts": alerts, "audit": audit}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-file", type=Path, required=True)
    args = parser.parse_args()
    base = [{"address": "demo-critical", "time_step": 48, "score": .91, "model_version": "xgb-graph-v1"}, {"address": "demo-high", "time_step": 48, "score": .63, "model_version": "xgb-graph-v1"}, {"address": "demo-monitor", "time_step": 48, "score": .21, "model_version": "xgb-graph-v1"}, {"address": "demo-missing", "time_step": 48, "score": .99, "model_version": "xgb-graph-v1", "missing_features": True}, {"address": "demo-critical", "time_step": 48, "score": .91, "model_version": "xgb-graph-v1"}]
    result = {"normal": process(base, model_available=True, max_alerts=3), "model_failure": process(base, model_available=False, max_alerts=3)}
    args.out_file.parent.mkdir(parents=True, exist_ok=True)
    args.out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
