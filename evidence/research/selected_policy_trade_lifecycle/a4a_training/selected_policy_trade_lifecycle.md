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
    "basis": "initial balance + completed position net PnL = final account equity + recorded payouts",
    "difference": 5.820766091346741e-11,
    "final_equity": 97845.68511833169,
    "initial_balance": 100000.0,
    "payout_event_rows": 0,
    "payout_sum": 0,
    "position_net_pnl_sum": -2154.3148816682547,
    "status": "matched"
  },
  "aggregate_pnl_reconciliation": {
    "difference": 5.502442945726216e-11,
    "position_net_pnl_sum": -2154.3148816682547,
    "reported_total_pnl": -2154.3148816683097,
    "status": "matched"
  },
  "cashflow_equity_reconciliation": {
    "allocated_entry_commission_total": 0.0,
    "basis": "initial balance plus chronological close-fill net PnL less recorded payouts; equity is checked only when flat",
    "checks": {
      "close_net_pnl_matches_exit_pnl_less_entry_commission": 1033,
      "flat_close_equity_matches_cumulative_cashflows": 987
    },
    "close_charge_checks": 1033,
    "close_fill_count": 1033,
    "completed_close_count": 987,
    "completed_close_equity_checks": 987,
    "ending_reconstructed_balance": 97845.68511833169,
    "failure_count": 0,
    "failures": {},
    "first_mismatch": null,
    "missing_columns": [],
    "open_fill_count": 987,
    "open_position_count_at_end": 0,
    "payout_count": 0,
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
    "decision_le_submission_le_fill": 987
  },
  "decision_to_submission_seconds": {
    "count": 987,
    "maximum": 60.0,
    "median": 60.0,
    "minimum": 60.0
  },
  "integrity_failure_count": 0,
  "integrity_status": "matched",
  "lifecycle_check_failures": {},
  "lifecycle_checks": {
    "fill_count_matches_event_rows": 987,
    "last_close_event_time_matches_position_exit_time": 987,
    "one_open_and_at_least_one_close": 987,
    "open_fill_matches_position_entry_time": 987,
    "position_marked_complete": 987
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
    "reported_total_economic_value": 97845.68511833169,
    "status": "not_applicable"
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
- Payout and total-economic-value reconciliation requires the recorded payout ledger and evaluation diagnostics; missing source fields are reported as incomplete.
- Repeated-payout cycle outcomes reconcile against payout, breach, and diagnostic ledgers when the corresponding events occur; missing linkage fields remain incomplete.
- Chronological cashflow/equity checks validate completed-close equity only when the account is flat; they do not reconstruct open-position mark-to-market or historical daily-risk state.
- This report is descriptive and does not identify causal loss mechanisms or economic superiority.

Input hashes and source paths are recorded in `evidence_manifest.json`.
