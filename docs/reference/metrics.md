# Evaluation metric definitions

New canonical run summaries carry the definition identifier
`qrl.performance_metrics.v2`. Annualized ratios still depend on the recorded
`periods_per_year` input; the general array API defaults to hourly bars while
the legacy pandas adapter defaults to 252 × 390 M1 bars. Preserve that basis
with the run protocol when comparing or regenerating results.

`evaluation.metrics.performance.compute_metrics` is the canonical aggregate
performance implementation. It consumes a chronological positive-equity
curve and optional completed-position PnLs. Callers must retain the resolved
metric inputs and sample scope with each result; a report should not silently
substitute zero for an undefined quantity.

## Equity-path metrics

| Metric | Definition and unit |
|---|---|
| Bar return | Simple change `equity[t] / equity[t-1] - 1`. If the first supplied valuation is not the opening balance, `compute_metrics` prepends `initial_balance` before computing returns and drawdown. |
| Sharpe | Sample mean of simple bar returns divided by sample standard deviation (`ddof=1`), annualized by `sqrt(periods_per_year)`. Fewer than two returns or zero dispersion returns `0`. |
| Sortino | Mean simple bar return divided by the root mean square of negative returns (nonnegative returns contribute zero), annualized by `sqrt(periods_per_year)`. Fewer than two returns or zero downside deviation returns `0`. |
| Calmar | Annualized compounded return divided by maximum drawdown. A zero drawdown returns `0`; duration is the number of return intervals divided by `periods_per_year`. |
| Maximum drawdown | Largest peak-to-trough loss relative to the running equity peak, returned as a positive fraction in `[0, 1]`. |
| Total PnL / return | `final_equity - initial_balance` in account currency, and that difference divided by `initial_balance` as a percent. |
| Breach count | Count supplied by the caller. The metric function cannot verify event identity or deduplicate events. |
| Breach rate | Supplied breach count divided by supplied session count, or `0` when the session count is zero. Interpret this as breached sessions only when the caller supplies a count of distinct breached sessions, rather than raw events. |

The general `compute_metrics` default annualization is 252 × 24 periods per
year. The pandas-compatible `calculate_metrics` adapter and
`evaluation_periods_per_year` preserve the legacy 252 × 390 M1 default unless
the configuration specifies another value. Therefore every reported Sharpe,
Sortino, and Calmar value must include the resolved frequency and bar interval;
the defaults are compatibility behavior, not evidence that either clock is
appropriate for a particular evaluation.

Daily chart helpers in `evaluation.plotting.plot_series` group by calendar
date in the equity index's timezone. They describe an index-date view and do
not establish the configured account session boundary or the simulator's
guardrail accounting. Do not label that series as authoritative daily-loss
exposure without validating the session mapping.

## Position metrics

Position-aware trade records aggregate realized fill legs once per completed
position, preferring a recorded position-level net PnL when present; otherwise
they sum each fill's `net_pnl`, falling back to `pnl`. Identified positions
without a completion event are excluded from completed-position statistics.
Records without a position ID retain the legacy one-record-per-trade rule.
Fill count and incomplete-position count are returned separately in the
adapter's extras.

| Metric | Definition and edge case |
|---|---|
| Trade count | Number of completed positions (plus legacy unpaired trade records), not the number of fills. |
| Profit factor | Sum of positive completed-position PnL divided by the absolute sum of negative PnL. With gains and no losses it is unbounded; when all outcomes are breakeven, both sums are zero and the ratio is undefined. With no completed positions the core record retains its compatibility zero, while reports mark it unavailable. |
| Win rate | Fraction of completed outcomes strictly greater than zero. Breakeven positions remain in the denominator and are not wins. |
| Expectancy / average trade | Arithmetic mean completed-position PnL in account currency. Both fields currently carry the same value; with no trades they are `0` in the core record. |
| Maximum consecutive loss | Longest run of completed-position PnLs below zero; a breakeven breaks the run. |
| Turnover | Completed-position count divided by the number of supplied equity values. This is a legacy count ratio, not notional turnover. |

`evaluation.metrics.trade_diagnostics` can derive OHLC-based MAE/MFE and
whether bars crossed logged stop/target levels for chart analysis. Those
excursions are not necessarily executable quote-side outcomes and must not be
reported as observed fill-level MFE/MAE when quote chronology is unavailable.

Sweep-delay reports count every open event, but mean and median delay are
`null` when no finite delay was observed. London/Asian percentages are `null`
when no entry has either level attribution; an attributed family with zero
entries remains a valid `0%` share.

## Uncertainty and reporting

`PerformanceMetrics` serializes `metric_definition_version` and the resolved
`periods_per_year` value. The standard summary table calls `n_trades`
“Completed Positions”; its numerator is the canonical completed-position PnL
series, while `extras.fill_count` and `extras.incomplete_positions` retain the
separate event counts. When there are no completed positions, the core numeric
record keeps its compatibility zeros, but summary tables render profit factor,
win rate, expectancy, and average trade as `N/A`; JSON reports store these
unavailable values as `null` and explain them in `metric_availability` as
`not_applicable_no_completed_positions`. Profit factor with positive gains and
no losses is unbounded in the numeric core record; reports render it as `N/A`
and store `null` with the reason
`unbounded_no_losses_with_positive_gains`, keeping serialized output valid
standard JSON. For a nonempty all-breakeven sample, profit factor is undefined;
reports render it as `N/A` and store `null` with the reason
`undefined_no_gains_or_losses`. Any other non-finite report metric is likewise
`null` with the reason `non_finite_metric_result`; report tables display it as
`N/A`.

The legacy Gate G3 report renders missing or non-finite Sharpe, drawdown, and
breach values as `N/A`, and a missing required value prevents a gate pass.
This behavior applies to the supported `metrics.json` and `training_log.json`
shapes; other historical report formats still require explicit provenance and
denominator review.

`evaluation.metrics.bootstrap` resamples bar returns in moving blocks and
reports within-path intervals. These intervals do not replace independent
training seeds, paired-seed uncertainty, chronological validation, or a
confirmatory holdout. Small or undefined samples must be reported explicitly;
in particular, a ratio returned as `0` by the computational contract is not
evidence of a zero economic effect.
The bootstrap point-statistic helpers reuse the core Sharpe, Sortino,
drawdown, and completed-trade win-rate implementations; bootstrap sampling
and its empty-sample `NaN` conventions remain specific to that module.

Specialized analyses such as action diversity, setup selection, exit reasons,
and cost attribution retain their own denominators. Per-idea and per-timeframe
trade summaries use the canonical completed-position win-rate and profit-factor
calculations; an unbounded profit factor is stored as `null` with an explicit
availability reason. See the [evaluation guide](../modules/evaluation.md) and the
[research validation protocol](../research/validation_protocol.md).
