# Operational Threshold Policy

Calibration was performed on the horizon-1 validation window only. The held-out test window was not used to choose the threshold.

- High-review threshold: `0.5713`
- Critical display threshold: `0.85`
- Below high threshold: monitor
- Critical and high alerts: human review
- Automatic blocks: `0`

The validation window contains only four positives. Threshold estimates are therefore inherently high-variance: this is a data-scarcity finding as much as a model-stability finding. The threshold is suitable for the prototype demonstration but requires recalibration with a larger, production-like validation stream before deployment.

Full candidate comparison: `reports/risk_ops_threshold_calibration.json`.
