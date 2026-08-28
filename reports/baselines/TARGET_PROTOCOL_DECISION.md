# Target protocol decision

The original target construction was revised after review.

## Corrections

- Right-censored windows are excluded. A horizon `k` now requires `t + k <= 49`.
- Unknown future activity is not treated as negative. Any future window containing class-3 activity is excluded.
- A negative example requires a complete future window with known activity and no illicit transaction.

## Resulting eligible examples

| Horizon | Eligible examples | Positives |
|---:|---:|---:|
| 1 | 7,511 | 45 |
| 3 | 17,280 | 73 |
| 5 | 19,190 | 85 |

These counts are substantially smaller than the initial protocol, but are more defensible. The downstream baseline results must be regenerated against these revised labels.
