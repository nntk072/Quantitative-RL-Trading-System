# Evaluation metrics and inference

**Status:** draft
**Use this when:** You need to reconstruct reported outcomes or choose the resampling unit for an evaluation comparison.

## Summary and use this when

Start with the account path, the execution ledger, and the declared period.
A metric computed from bars answers a different question from a statistic
computed over completed positions or independent training seeds.

- Use the equity series for path returns and drawdown.
- Use completed-position PnL for trade statistics and keep realized fill counts.
- Use matched chronological observations for within-path comparison.
- Use independent paired training seeds for the prospective primary contrast.

## Key terms

- [Drawdown, OOS and walk-forward](../../glossary.md)
- [Performance metrics and units](../../reference/metrics.md)
- [Period role and the primary outcome](../../research/validation_protocol.md)

## Explanation

### The rule

`compute_metrics` accepts an equity path, realized trade PnLs and an explicit
annualization cadence. Its bar-return Sharpe and Sortino use the declared
periods per year. The cadence must describe the actual sampled series. An
account session return has its own definition and can be unavailable even
when the bar equity series is usable.

`completed_position_trade_pnls` returns one PnL per completed position when
its PnL is reconstructible. A partial exit with usable PnL contributes to
the realized fill count. The incomplete-position count includes every
observed position ID without a reconstructible completed PnL. That includes
open positions and final-closed positions with unusable PnL evidence.
Inspect the ledger schema before reconstructing legacy trade counts from
individual close rows.

The prospective primary outcome is economic value over the full path. Add
cumulative payouts to ending retained equity, subtract initial operating
equity, and divide by initial operating equity. Keep retained ending equity
and payouts visible in the report so withdrawals can be reconciled.

### Why the units differ

One equity path contains serially ordered returns. The paired moving-block
bootstrap uses the same contiguous indices for treatment and control in each
draw so both arms retain their time pairing. Its interval describes path
uncertainty at the specified block length.

The primary research comparison uses one full-path treatment-minus-control
difference per independent training seed. A seed pair includes two defined
arms with matched evaluation context. More fills or sessions in either arm
leave the number of independent seed pairs unchanged.

### Failure modes

- A frequency copied from a different timeframe changes annualized ratios.
- A ledger can show realized fills and few completed trades when positions
  remain open or completed PnL cannot be reconstructed.
- Equal series lengths can conceal different dates, gaps or ordering.
- Payouts observed first at a new session boundary can make daily returns
  ambiguous even when the final cumulative payout is known.
- A favorable confidence interval cannot clear a hard-risk gate.

## Worked example

The Tier A notebook groups three synthetic closing legs by position, checks
drawdown on a four-row equity sequence and computes one payout-aware path
return. It uses the same indices on two small return vectors for a paired
statistic.

```{toctree}
:hidden:

examples/evaluation-metrics-inference
```

## Tasks

- Reconcile totals against the [metrics definitions](../../reference/metrics.md).
- For replay inputs and ledgers, use the [evaluation methodology](../../research/evaluation_methodology.md).
- Freeze replication units and inference settings under the [validation protocol](../../research/validation_protocol.md).
- Review the [cross-metric contract](../../reference/subjects/evaluation-metrics-inference.md).

## Contract

| Quantity | Inputs and interpretation | Source |
|---|---|---|
| Drawdown | Largest fractional decline from the running equity peak | `evaluation/metrics/performance.py::max_drawdown` |
| Completed-position trade count | Closed positions with reconstructible PnL on the position-aware path | `evaluation/metrics/performance.py::completed_position_trade_pnls` |
| Incomplete-position count | Observed position IDs without a reconstructible completed PnL | `evaluation/metrics/performance.py::completed_position_trade_pnls` |
| Annualized ratios | Bar returns with a positive integer annualization factor | `evaluation/metrics/performance.py::compute_metrics` |
| Paired temporal interval | Same contiguous return indices across both arms for each bootstrap draw | `evaluation/metrics/bootstrap.py::paired_metric_difference_ci` |
| Paired seed interval | Resample paired full-path differences with replacement for the mean | `scripts/research/analysis/evidence/analyze_paired_seed_results.py::analyze_paired_seed_metrics` |

## Verify

- `tests/unit/evaluation/test_metrics.py` covers metric behavior, including
  closed records with unusable PnL.
- `tests/integration/test_matched_comparison.py` directly tests
  `compare_matched_returns` with timestamp, provenance and intervention checks.
- `tests/unit/evaluation/test_matched_comparison.py` covers paired equity
  intervals and their reporting records.
- `tests/integration/test_bootstrap_drawdown_interval.py` covers the drawdown
  interval.
- `tests/unit/research/test_paired_seed_statistics.py` covers paired seed
  reports and sign-flip inference.
- Current empirical metrics are **not measured** in the
  [findings register](../../research/findings_register.md).

## Limits and common mistakes

- Record the input sampling period and the number of observations with each
  annualized ratio. Dependence and changing volatility remain relevant.
- Report a count and an availability reason for a metric requiring a
  complete account path.
- A zero-trade path still has an account path and a survival outcome.
- Bootstrap settings and the resampling unit determine the question the
  interval answers. An interval over seeds leaves time-path dependence
  within each seed unchanged.
- State the fraction or currency unit explicitly, including whether reported
  drawdown magnitude uses a positive sign convention.

## Change checklist

- Identify the authoritative equity and ledger inputs for the metric.
- Verify the annualization cadence, starting balance and equity definition.
- Reconcile incomplete counts with position status and PnL availability.
- Check timestamp equality and provenance before temporal pairing.
- Preserve seed IDs, arm run IDs, per-seed differences and inference settings.
- Keep survival, cost and no-trade outcomes visible beside return.

## Review procedure

1. List the timestamp range, role, execution model and path length from the
   manifests and retained ledger. Verify the window before calculating ratios.
2. Identify which account row supplies the initial and ending values. Check
   the payout ledger against the ending cumulative payout figure.
3. Locate at least one peak-to-trough segment. Reconcile its drawdown using
   the same equity definition as the metric.
4. Group partial realizations by position identity and check for the complete
   close marker and usable PnL. Use the position ledger for remaining exposure.
5. Read the metric availability fields before writing a table. Distinguish
   an observed zero from an ambiguous payout boundary or missing trace.
6. Compare treatment and control timestamps in order and confirm their
   provenance. Record the number of paired observations and bootstrap settings.
7. Compare treatment and control at the seed level using the registered full
   path outcome. Preserve missing, invalid and breached outcomes in the ledger.
8. Review the survival gate and selection history before interpreting the
   reported interval. Follow the period role recorded before the comparison.
9. Link the finished report to the exact metrics and ledgers used for any
   recomputation, including hashes and the metric revision.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `evidence_reporting_engineer`
