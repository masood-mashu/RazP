# Razorpay AI Builder 2026 — Track 2 Demo Runbook

## One-line story

Use the transaction graph observed so far to rank actors who may show illicit activity next, then route alerts to human review with evidence and safe fallbacks.

## Start the demo

Clone the repository, install dependencies, and open two terminals:

```bash
git clone https://github.com/masood-mashu/RazP.git
cd RazP
python -m pip install -r requirements.txt
```

Window 1 — dashboard:

```powershell
python -m http.server 8765 --directory demo
```

Window 2 — API:

```powershell
python api/risk_api.py --artifact demo/data/risk_ops_snapshot.json --model-file models/xgb_graph_horizon1.json --metadata-file models/xgb_graph_horizon1.metadata.json --port 8766
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/).

## Suggested 3-minute walkthrough

1. Start on Overview. Say: “The selected detector is graph-enhanced XGBoost at horizon 1. Its rolling-origin mean AP is 0.0677, slightly above the temporal GNN ablation at 0.0650.”
2. Point to “No auto-blocks”. Say: “This is decision support: critical and high signals go to a human reviewer.”
3. Open Alert queue. Click the top alert. Point out the score, risk band, evidence chips, model version, and audit trail.
4. Choose Connect API. Say: “The queue is available through the local API, and individual feature vectors can now be scored by the saved horizon-1 model; the recorded artifact remains the reproducible fallback.”
5. Open Failure test and choose Simulate model failure. Say: “When the model is unavailable, the system does not block or silently drop work; it falls back to rules-only monitoring.”
6. Close with: “The next production step is replacing the artifact-backed adapter with a model-serving process after threshold and calibration review.”

## What the numbers mean

- Primary detector: graph-enhanced XGBoost.
- Primary horizon: one timestep ahead.
- Evaluation: rolling temporal continuation folds.
- Reported metric: average precision, appropriate for the rare-positive setting.
- Alert queue: top 50 recorded predictions from the held-out continuation window.
- Automatic blocks: zero.
- Threshold policy: high review at `0.5713`; critical display at `0.85`.

## Safe claims

Say “ranked early-warning signal” and “routes to human review.” Do not say the system proves criminality, blocks customers, or is production-ready. The API supports real-time inference from feature vectors, while the queue remains backed by recorded predictions for reproducibility.

## Stop

Press `Ctrl+C` in both PowerShell windows.
