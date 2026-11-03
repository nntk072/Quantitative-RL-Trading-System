# Selected policy trade lifecycle

This is a descriptive reconciliation of decision, fill, and position records in the `training` partition. The source manifest marks the associated holdout as previously inspected. It makes no causal or economic-superiority claim.

## Coverage

- Recorded policy/action rows: 53,629
- Recorded fill-event rows: 1,678
- Completed positions: 825 / 825
- Positions with linked fill events: 825
- Unlinked fill position IDs: 0
- Positions with holding duration: 825
- Recorded position window (UTC): 2024-12-30T13:50:00.071000+00:00 to 2025-10-28T16:30:45.928000+00:00
- Mean / median recorded holding seconds: 3065.541998787879 / 636.317

### Decision event types

- `close`: 82
- `eod_close`: 125
- `open`: 825
- `reject`: 51,457
- `sl_update`: 153
- `stop_close`: 496
- `tp_close`: 122
- `tp_partial_close`: 28
- `tp_update`: 341

### Position exit reasons

- `ema_21_exit`: 82
- `session_end`: 125
- `structure_sl`: 496
- `structure_tp3`: 122

## Reconciliation checks

```json
{
  "account_equity_reconciliation": {
    "basis": "initial balance + completed position net PnL = final equity; no payout rows recorded",
    "difference": 5.820766091346741e-11,
    "final_equity": 89943.95098700203,
    "initial_balance": 100000.0,
    "payout_event_rows": 0,
    "position_net_pnl_sum": -10056.049012997908,
    "status": "matched"
  },
  "aggregate_pnl_reconciliation": {
    "difference": 6.548361852765083e-11,
    "position_net_pnl_sum": -10056.049012997908,
    "reported_total_pnl": -10056.049012997973,
    "status": "matched"
  },
  "decision_order_checks": {
    "decision_le_submission_le_fill": 825
  },
  "decision_to_submission_seconds": {
    "count": 825,
    "maximum": 60.0,
    "median": 60.0,
    "minimum": 60.0
  },
  "lifecycle_checks": {
    "fill_count_matches_event_rows": 825,
    "last_close_event_time_matches_position_exit_time": 825,
    "one_open_and_at_least_one_close": 825,
    "open_fill_matches_position_entry_time": 825,
    "position_marked_complete": 825
  },
  "pnl_reconciliation_checks": {
    "close_fill_net_pnl_matches_position": 825,
    "initial_plus_position_net_pnl_matches_final_equity": 1,
    "position_net_pnl_matches_reported_total": 1
  }
}
```

## Limits

- Recorded decision/order/fill timestamps reconcile logged events but do not establish authoritative feed chronology or executable quote availability.
- Decision-to-submission gaps are descriptive; they may reflect bar-label versus completed-bar availability semantics rather than agent or network latency.
- Candidate detection and eligibility before recorded policy decisions are not fully linked by these CSVs.
- Per-position MFE and MAE are not present in the required source columns and are not derived by this report.
- Aggregate equity reconciliation is only attempted when metrics, complete position net PnL, and a no-payout ledger are available; other cash-flow and reset semantics remain outside this check.
- This report is descriptive and does not identify causal loss mechanisms or economic superiority.

Input hashes and source paths are recorded in `evidence_manifest.json`.
