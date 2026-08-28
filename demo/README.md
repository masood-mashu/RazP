# Risk Operations Demo

This static, review-first surface connects the measured rolling-origin outputs to the selected graph-enhanced XGBoost detector. It shows the planned alert policy, evidence display, and safe failure behavior.

The dashboard loads `data/risk_ops_snapshot.json` at startup. This recorded artifact contains the model version, measured AP values, policy, and controlled alert cases used for the demo. It is intentionally versioned and offline-friendly; no live customer or payment data is sent anywhere.

## Run API mode

From the project root, start the API in a second PowerShell window:

```powershell
& "C:\Users\Masood\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" api\risk_api.py --artifact demo\data\risk_ops_snapshot.json --model-file models\xgb_graph_horizon1.json --metadata-file models\xgb_graph_horizon1.metadata.json --port 8766
```

Keep the dashboard server running on port `8765`, open the dashboard, and choose `Connect API`. If the API is unavailable, the dashboard remains in recorded mode.

API endpoints: `/health`, `/metrics`, `/alerts`, and `POST /score` with `{ "address": "...", "time_step": 46 }`.

The alert queue is intentionally a controlled demo scenario; it is not a live scoring feed. Open `index.html` directly or serve this folder with a local static web server.
