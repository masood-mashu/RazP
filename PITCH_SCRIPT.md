# Five-Minute Pitch Script

## 0:00–0:45 — Problem

“Transaction-by-transaction fraud detection misses coordinated abuse. Several accounts can look normal individually while their transaction neighborhood and recent behavior reveal an emerging illicit pattern. Our project asks a different question: using the graph observed so far, which actors are likely to show illicit activity next?”

## 0:45–1:25 — Why graph and time matter

“We preserve the temporal structure of Elliptic++. For each actor, we build recent activity, cumulative behavior, counterparties, new links, and graph degree. The target is future illicit activity, so the model cannot use information from the future.”

## 1:25–2:10 — Model selection

“We compared rules, causal-feature XGBoost, graph-enhanced XGBoost, and a temporal GNN ablation. The primary model is graph-enhanced XGBoost with horizon 1. Its rolling mean average precision is 0.0677 versus 0.0650 for the GNN. The horizon-1 base rate is 1.17%, so the primary result is about 5.8 times the random baseline.”

## 2:10–3:05 — Live demo

“This is the risk-operations console. The alert queue ranks actors, shows the score and risk band, and exposes evidence such as activity, counterparties, and new links. Critical and high signals go to human review. The system does not automatically block.”

Show Overview, Alert queue, one alert detail, then Live score and Connect API.

## 3:05–3:55 — What broke and what we learned

“We stress-tested threshold selection across five rolling validation folds. There were only 25 known positives, and the selected threshold varied from 0.0162 to 0.6620. That is a data-scarcity finding as much as a model-stability finding. We therefore gate the project as research-only and keep a human in the loop.”

## 3:55–4:35 — Operations realism

“We also tested analyst capacity. In a seeded 20,000-row proxy, 10 alerts per batch captured about 33% of known positives, while 100 captured about 76%. This makes the tradeoff explicit: model quality is not enough; the alert queue must match the team that operates it.”

## 4:35–5:00 — Close

“The result is not an autonomous blocking system. It is a measured, explainable early-warning workflow with safe fallbacks. Before production, we need authorized representative data, threshold calibration, shadow mode, monitoring, audit storage, and security review. Our strongest decision is knowing exactly why we are not enabling automatic action yet.”
