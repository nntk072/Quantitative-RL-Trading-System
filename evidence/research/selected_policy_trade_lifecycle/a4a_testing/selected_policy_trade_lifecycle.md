# Selected policy trade lifecycle

This is a descriptive reconciliation of decision, fill, and position records in the `testing` partition. The source manifest marks the associated holdout as previously inspected. It makes no causal or economic-superiority claim.

## Coverage

- Recorded policy/action rows: 54,416
- Recorded fill-event rows: 411
- Completed positions: 203 / 203
- Positions with linked fill events: 203
- Unlinked fill position IDs: 0
- Positions with holding duration: 203
- Recorded position window (UTC): 2026-01-02T14:05:00.028000+00:00 to 2026-03-30T14:43:00+00:00
- Mean / median recorded holding seconds: 3158.14239408867 / 490.997

### Decision event types

- `close`: 14
- `eod_close`: 32
- `forced_close`: 1
- `open`: 203
- `reject`: 53,896
- `sl_update`: 20
- `stop_close`: 118
- `tp_close`: 38
- `tp_partial_close`: 5
- `tp_update`: 89

### Position exit reasons

- `ema_21_exit`: 14
- `max_drawdown`: 1
- `session_end`: 32
- `structure_sl`: 118
- `structure_tp3`: 38

## Reconciliation checks

```json
{
  "account_equity_reconciliation": {
    "basis": "initial balance + completed position net PnL = final account equity + recorded payouts",
    "difference": -2.9103830456733704e-11,
    "final_equity": 89998.38242865316,
    "initial_balance": 100000.0,
    "payout_event_rows": 0,
    "payout_sum": 0,
    "position_net_pnl_sum": -10001.617571346873,
    "status": "matched"
  },
  "aggregate_pnl_reconciliation": {
    "difference": -3.2741809263825417e-11,
    "position_net_pnl_sum": -10001.617571346873,
    "reported_total_pnl": -10001.61757134684,
    "status": "matched"
  },
  "cycle_reconciliation": {
    "checks": {},
    "event_rows": 0,
    "failure_count": 0,
    "failure_rows": 0,
    "failures": {},
    "missing_columns": [],
    "missing_failure_link_columns": {},
    "reported_cycle_count": 1.0,
    "status": "not_applicable",
    "success_rows": 0
  },
  "decision_order_checks": {
    "decision_le_submission_le_fill": 203
  },
  "decision_to_submission_seconds": {
    "count": 203,
    "maximum": 60.0,
    "median": 60.0,
    "minimum": 60.0
  },
  "integrity_failure_count": 0,
  "integrity_status": "matched",
  "lifecycle_check_failures": {},
  "lifecycle_checks": {
    "fill_count_matches_event_rows": 203,
    "last_close_event_time_matches_position_exit_time": 203,
    "one_open_and_at_least_one_close": 203,
    "open_fill_matches_position_entry_time": 203,
    "position_marked_complete": 203
  },
  "payout_reconciliation": {
    "checks": {
      "payout_rows_match_cycle_successes": 1,
      "payout_sum_matches_reported_cumulative": 1
    },
    "ending_total_economic_value_curve": null,
    "event_rows": 0,
    "failure_count": 0,
    "failures": {},
    "missing_columns": [],
    "payout_sum": 0,
    "reported_cumulative_payouts": 0.0,
    "reported_cycle_successes": 0.0,
    "reported_total_economic_value": 89998.38242865316,
    "status": "not_applicable"
  },
  "pnl_reconciliation_checks": {
    "close_fill_net_pnl_matches_position": 203,
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
- Payout and total-economic-value reconciliation requires the recorded payout ledger and evaluation diagnostics; missing source fields are reported as incomplete.
- Repeated-payout cycle outcomes reconcile against payout, breach, and diagnostic ledgers when the corresponding events occur; missing linkage fields remain incomplete.
- This report is descriptive and does not identify causal loss mechanisms or economic superiority.

Input hashes and source paths are recorded in `evidence_manifest.json`.
