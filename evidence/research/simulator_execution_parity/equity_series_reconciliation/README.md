# Saved equity-series report reconciliation

This packet independently recalculates the saved A4 training and testing
return and maximum drawdown metrics from each run's timestamped `equity.csv`,
then compares them with `metrics.json`. It reads the retained reanalysis
artifacts; it does not replay a policy or regenerate a campaign result.

All four reports matched. Each training series has 99,493 valid observations;
each testing series has 79,070. All timestamp sequences are strictly
increasing. For both arms and partitions, the first equity matches initial
balance, the last equity matches final equity, and recalculated total return
and maximum drawdown match the saved metrics within the declared floating-point
tolerance. Per-run outputs record input paths, byte counts, and SHA-256 hashes.

Both pinned source configs declare `trading_policy.mode: legacy`. In that mode,
the account's daily-loss counter sums the absolute values of negative realized
close PnL; it does not measure the drop from a daily equity reset point. The
reusable `audit_gross_realized_loss_counter.py` therefore reconstructs
the counter from raw `pnl` fields on saved close rows and compares the threshold
crossing with `breach_events.csv`. A4A crosses $5,000 on a March 6 stop close at
17:15:29 UTC; its recorded daily-loss event follows at 17:17:00.118 UTC, with
$5,017.66 of gross realized losses through the recorded event. A4B crosses at
17:31:12 UTC; its event follows at 17:33:00.078 UTC, with $5,399.25 through the
event. Each training run has one source-session crossing (session ID 47) and
one matching recorded event. No other mapped session crosses $5,000 without a
recorded event.
The testing partitions contain no `daily_loss` events.

The earlier first-sample-to-calendar-date-minimum screen was not an account
reset reconciliation. The new
[session equity daily-loss screen](session_equity_daily_loss_screen.md) maps all
four saved equity series to the verified configured M1 date/session labels and
anchors each session from the initial balance or prior session's last equity
sample, matching the pinned reset-before-mark-to-market order. Across 259
training sessions per arm and 205 report-period sessions per arm, no serialized
session equity sample fell below the $5,000 (5%) daily floor; equality is
allowed. The closest training
session was A4A session 68 at a $4,972.04 observed loss. The exact-matching and
date-fallback row counts, per-session anchors, and inputs are recorded in each
machine report under `observed_session_equity_risk_screen`.

The historical gross realized-loss counter events in session 47 occurred with
observed session-net equity declines of $3,004.28 / $3,389.32 for A4A / A4B.
This explains why the recorded gross-loss events do not correspond to breaches
of the current session-net equity rule. Since those historical events blocked
later entries, the saved equity path cannot show what would have happened if
the current rule had allowed those entries. The session screen is therefore a
bounded observed-path result, not a counterfactual replay or policy-quality
claim. It uses the supplied local session dates and makes no external-calendar
claim.

Across all supplied equity rows, the first-observation-to-daily-minimum screen
covered 259 calendar dates per training arm and 205 per testing arm. No date
had a sampled decline at or above $5,000, and there were no unrecorded
first-sample crossings. This remains a screening result: the first sample on a
date is not independently proven to equal the account's daily reset equity.
The sampled-date audit now counts equality separately from a strict crossing:
exactly $5,000 is at the floor and remains allowed; only a decline greater than
$5,000 is reported as exceeding the limit. The four preserved reports were
regenerated from their hash-linked source runs and continue to show zero dates
at or above the limit and zero strict crossings. A synthetic regression checks
both exact equality and a $5,000.01 crossing.

This closes serialized equity-series metric reproduction, source-session
reconciliation of gross-realized-loss arithmetic to recorded events, and a
bounded session-net daily-loss screen of the preserved equity paths. It does
not independently reconstruct mark-to-market equity from every quote, replay
the counterfactual actions blocked by the historical policy, reconcile all
cashflows with fills, validate full simulator behavior, or establish policy
quality. Those Stage E gates remain open.

Reproduce the equity reports with
`audit_recorded_equity_series.py --run-dir <run-directory> --output <report>`
and the trade-ledger reports with
`audit_gross_realized_loss_counter.py --run-dir <run-directory> --output <report>`.
The run directories and validation commands are recorded in `run_metadata.json`.
The focused equity-series tests pass 12/12, including session reset anchoring,
date-based fallback for sub-bar execution timestamps, and equality-allowed
daily-floor breach behavior, plus sampled-date exact-equality and strict-crossing
semantics; the trade-ledger test
passes 1/1. Scoped Ruff format/check and `git diff --check` pass.

The initial cache-only identity preflight in
[`saved_equity_bar_identity.md`](saved_equity_bar_identity.md) found that
Parquet-loaded frame hashes differed from the saved in-memory fingerprints.
The follow-up
[`source_reconstructed_bar_identity.md`](source_reconstructed_bar_identity.md)
rebuilds all four splits from each run's configured raw M1 input and saved
config; every reconstructed frame exactly matches both the original run and
reanalysis manifests. The Parquet hash difference is retained and explained,
and subsequent reconciliation must use the verified raw-rebuilt frames. This
resolves the saved-bar identity gate only; serialized-ledger mark-to-market and
cashflow reconciliation remain open.

## Saved equity to raw-bar and fill reconstruction

The reusable `scripts/research/analysis/evaluation/reconcile_saved_equity_to_fills.py`
reconstructs the four preserved A4 equity paths from the exact raw-rebuilt M1
frames, saved account config, and identified fill events. At valuation time
`T`, it follows `TradingEnv` ordering: mark the pre-existing position from the
bar at `floor(T - 1 minute)`, then process fills through `T`. Cash is calculated
from fill prices and quantities; saved fill PnL is used only as an independent
arithmetic comparison, never as the cashflow input. Long positions mark to bid,
short positions to ask, and any remainder after a partial close marks at that
close-side fill quote, matching `Broker.close_position`.

All 357,126 of 357,126 equity rows reproduce within the declared $0.000001
tolerance. The maximum absolute difference is below $0.000000001 in every
partition; the maximum recorded-close PnL arithmetic difference is below
$0.000000000001. All four raw frame hashes match the saved in-memory manifests;
all fill events are consumed, all bar timestamps map, the terminal inventory is
flat in every partition, and there are no quantity or calculation errors. The
machine report records the per-partition inputs, hashes, observation coverage,
residual summaries, and largest residual rows in
`equity_fill_reconciliation.json`.

This closes the serialized A4 fill-to-cash/position-to-mark-to-market equity
reconciliation slice. It does not replay policy actions, prove the
counterfactual under the current daily rule, reconstruct intrabar account
excursions between the saved M1 observations, establish external feed/calendar
parity, or establish policy quality. The 2026 testing partitions remain
exploratory. Reproduce with
`.venv/bin/python scripts/research/analysis/evaluation/reconcile_saved_equity_to_fills.py`
inside the existing compatible GH200 allocation; the report's script and input
hashes are anchored by this packet's `SOURCE_SHA256SUMS` and `SHA256SUMS`.
