# Selected policy trade lifecycle

This is a descriptive reconciliation of decision, fill, and position records in the `training` partition. The source manifest marks the associated holdout as previously inspected. It makes no causal or economic-superiority claim.

## Coverage

- Recorded policy/action rows: 49,271
- Recorded fill-event rows: 2,020
- Completed positions: 987 / 987
- Positions with linked fill events: 987
- Unlinked fill position IDs: 0
- Positions with holding duration: 987
- Recorded position window (UTC): 2024-12-30T13:50:00.071000+00:00 to 2025-12-31T19:56:34.425000+00:00
- Mean / median recorded holding seconds: 3095.773954407295 / 670.655

### Decision event types

- `close`: 83
- `eod_close`: 151
- `open`: 987
- `reject`: 46,719
- `sl_update`: 148
- `stop_close`: 585
- `tp_close`: 168
- `tp_partial_close`: 46
- `tp_update`: 384

### Position exit reasons

- `ema_21_exit`: 83
- `session_end`: 151
- `structure_sl`: 585
- `structure_tp3`: 168

## Reconciliation checks

```json
{
  "account_equity_reconciliation": {
    "basis": "initial balance + completed position net PnL = final equity; no payout rows recorded",
    "difference": 5.820766091346741e-11,
    "final_equity": 97845.68511833169,
    "initial_balance": 100000.0,
    "payout_event_rows": 0,
    "position_net_pnl_sum": -2154.3148816682547,
    "status": "matched"
  },
  "aggregate_pnl_reconciliation": {
    "difference": 5.502442945726216e-11,
    "position_net_pnl_sum": -2154.3148816682547,
    "reported_total_pnl": -2154.3148816683097,
    "status": "matched"
  },
  "decision_order_checks": {
    "decision_le_submission_le_fill": 987
  },
  "decision_to_submission_seconds": {
    "count": 987,
    "maximum": 60.0,
    "median": 60.0,
    "minimum": 60.0
  },
  "lifecycle_checks": {
    "fill_count_matches_event_rows": 987,
    "last_close_event_time_matches_position_exit_time": 987,
    "one_open_and_at_least_one_close": 987,
    "open_fill_matches_position_entry_time": 987,
    "position_marked_complete": 987
  },
  "pnl_reconciliation_checks": {
    "close_fill_net_pnl_matches_position": 987,
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
