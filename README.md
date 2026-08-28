# Razorpay AI Builder 2026 — AI Risk Manager

Temporal early-warning detection for emerging illicit activity in transaction networks.

## What this project does

The system uses transaction history and graph structure observed up to time `t` to rank actors who may show illicit activity in a future window. It is designed as analyst decision support: alerts include evidence and route to human review. Automatic blocking is deliberately disabled.

The primary detector is graph-enhanced XGBoost at horizon 1. A temporal GNN was evaluated as an ablation but did not exceed the simpler primary model.

## Current result

- Horizon-1 rolling mean AP: `0.0677`
- Horizon-1 pooled test base rate: `1.17%`
- Lift over random baseline: approximately `5.8×`
- Precision@50: `2.0%`
- Recall@50: `5.3%`
- Automatic blocks: `0`

The prototype is research-only. Elliptic++ is a public benchmark, not Razorpay production data. Threshold stability and alert volume require a representative authorized validation stream before deployment.

## Run the demo

Clone the repository and enter its directory:

```bash
git clone https://github.com/masood-mashu/RazP.git
cd RazP
```

Install the API and model dependencies once:

```bash
python -m pip install -r requirements.txt
```

Open two terminal windows from the cloned repository directory.

Dashboard:

```powershell
python -m http.server 8765 --directory demo
```

API with real-time inference:

```powershell
python api/risk_api.py --artifact demo/data/risk_ops_snapshot.json --model-file models/xgb_graph_horizon1.json --metadata-file models/xgb_graph_horizon1.metadata.json --port 8766
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/).

For the presentation flow, use [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md).

## Run tests

```powershell
python -m unittest discover -s tests -v
```

## Repository map

- `data/raw/` — original local dataset; do not commit large/private source files.
- `data/processed/` — leakage-safe labels, splits, features, snapshots, and proxy artifacts.
- `models/` — saved primary inference model and metadata.
- `tools/` — audit, preprocessing, evaluation, calibration, and artifact-building scripts.
- `api/` — local scoring API.
- `demo/` — static risk-operations dashboard.
- `reports/` — experiment results, policies, readiness notes, and plots.
- `tests/` — API safeguard tests.

The demo and API run entirely from committed artifacts in `models/` and `demo/data/`; the raw dataset is not required to run the submission. To reproduce the full pipeline, download Elliptic++ from the [official repository](https://github.com/git-disl/EllipticPlusPlus) and place it under `data/raw/ellipticplusplus/`.

## Further context

- [Complete project context](PROJECT_CONTEXT.md)
- [Architecture documentation](ARCHITECTURE.md)
- [Five-minute pitch script](PITCH_SCRIPT.md)
- [Production validation gate](reports/PRODUCTION_VALIDATION_GATE.md)
