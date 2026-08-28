# Shadow Mode Plan

Shadow mode scores the full available temporal benchmark but triggers no customer, analyst, or blocking action.

## What it measures

- Score distribution across timesteps.
- High/critical alert volume.
- Score concentration and drift indicators.
- Operational load under the current threshold.

## Safety boundary

This is telemetry only. It is not a substitute for a representative Razorpay validation stream, and its rows must not be mixed into threshold calibration or test evaluation.

Run output: `reports/shadow_mode_summary.json`.
