# Production Validation Gate

This assessment uses the available Elliptic++ rolling-origin validation windows as a production-like proxy. It is not live Razorpay traffic and does not authorize deployment.

## Gate result

`RESEARCH_ONLY`

The horizon-1 threshold is not stable enough to freeze for production. Validation positives are sparse, and fold-level thresholds vary materially. The model can continue to support the prototype demo with human review and zero automatic blocks.

## Required evidence before deployment

- A representative, larger validation stream with stable label availability.
- Threshold calibration against expected analyst capacity and alert-rate targets.
- Monitoring for recall, alert rate, missing features, drift, and model availability.
- A shadow-mode period before any customer-impacting action.
- Explicit approval before enabling any automated block.

Full fold-level values are in `reports/threshold_stability_assessment.json`.
