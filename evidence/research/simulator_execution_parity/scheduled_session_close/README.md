# Scheduled session-close parity

This packet checks a controlled TickBook close at the final NY bar against the
environment and event-driven backtest. The synthetic fixture has six NY bars,
two following Asia bars, distinct quote prices near the close, and prescribed
long-entry/hold actions. It is an execution-contract regression, not a local
feed sample, learned-policy replay, or economic result.

The first trace exposed a submission-window mismatch: the environment submits
at the final NY bar's start and selects the first executable quote through the
bar-end deadline; the backtest had submitted at bar end. The backtest now uses
the same deadline resolver. A stable event-keyed latency stream also keeps the
scheduled-close arrival identical across engines despite different per-bar RNG
draw counts. Both engines close at 13:35 UTC at 101.0 in the zero-latency
fixture, with $0.80 realized PnL and $50,000.80 ending equity. Zero and 30 ms
latency cases include distinct quotes 5, 10, 20, and 25 ms after submission;
both engines select the same sub-minute quote and reconcile PnL/equity in each
case.

## Files

- `scheduled_session_close.json`: regenerated controlled trace.
- `scheduled_session_close_verification.json`: independent numeric, deadline,
  fixture, and current-source-byte verification.
- `OUTPUT_SHA256SUMS`: checksums for both reports, this README, and both scripts.

## Reproduction

```bash
.venv/bin/python scripts/research/analysis/evaluation/compare_scheduled_session_close.py
.venv/bin/python scripts/research/analysis/evaluation/verify_scheduled_session_close.py
```

The report records all synthetic bar and TickBook inputs with a canonical
fixture hash, both engines' entry/close event fields, latency validity, final
account state, and source hashes. The independent verifier recomputes those
checks from the saved report and current source bytes. This verifies the
scheduled-close event only; other event types and full lifecycle parity remain
open.
