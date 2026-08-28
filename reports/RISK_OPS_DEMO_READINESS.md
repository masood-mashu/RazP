# Risk-Operations Demo Readiness

Status: ready for local walkthrough.

## Verified

- Dashboard loads the versioned prediction artifact.
- 50 ranked actor-level alerts are displayed.
- Model and threshold metadata are present.
- Alert detail exposes score, band, evidence, action, and audit trail.
- API `/health`, `/metrics`, `/alerts`, and `/score` respond.
- Unknown actor requests return monitor-only output with score `0.0`.
- Dashboard API mode connects as `xgb-graph-v1`.
- Recorded mode remains available when API mode cannot connect.
- Model-failure simulation keeps automatic blocks at zero.
- Four API safeguard tests pass.

## Scope boundary

The API serves the reproducible queue from `demo/data/risk_ops_snapshot.json` and supports real-time horizon-1 inference when launched with `models/xgb_graph_horizon1.json` and its metadata file. It remains a research prototype, not a production deployment.

## Presentation risk

The dataset is an illicit-activity research benchmark, not live Razorpay traffic. The demo must be presented as a research prototype and decision-support workflow.
