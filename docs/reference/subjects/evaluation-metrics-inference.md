# Evaluation metrics and inference contract

**Status:** draft
**Scope:** Account-path, fill and replication units used together in an evaluation report.

| Output | Unit and input | Availability or interpretation |
|---|---|---|
| Maximum drawdown | Positive fraction from a running equity peak | Report the equity definition and window. |
| Annualized Sharpe and Sortino | Simple bar returns with a positive integer periods-per-year input | Use the cadence of the returned series on both sides of a comparison. |
| Trade PnLs | Net currency per completed position with reconstructible PnL when position IDs exist | A valid position summary takes precedence over summing the legs. |
| Incomplete-position count | Observed position IDs without a reconstructible completed PnL | Includes open positions and final-closed positions with unusable PnL evidence. Use the position ledger to verify open exposure. |
| Account-session returns | Session opening and closing economic value from the complete account trace | A payout whose session attribution is ambiguous can leave the daily statistic unavailable. |
| Primary economic return | (Ending retained equity + cumulative payouts − initial operating equity) / initial operating equity | Use the full declared path and report the hard-risk outcome. |
| Paired path interval | One shared block index sequence per draw on aligned, finite returns | Interprets within-path sampling at the chosen block length. |
| Paired seed interval | One difference for each independent seed pair | The prospective primary interval uses 10,000 percentile draws with RNG seed 42. |

In the position-aware path, valid position-level net summaries or summed
finite close legs contribute once per completed position. Legacy records
without position IDs retain the one-record-per-trade convention. Preserve
the provenance for any comparison across ledger versions.

Record an interval's point estimate, bounds, unit, confidence level, draw
count, RNG seed, and block length when applicable. Keep the period role,
replicate count and missing-metric reasons with the result.

Sources are `evaluation/metrics/performance.py`,
`evaluation/metrics/bootstrap.py` and
`scripts/research/analysis/evidence/analyze_paired_seed_results.py`.
See the [validation protocol](../../research/validation_protocol.md)
and [subject guide](../../subjects/E_evaluation_research/evaluation-metrics-inference.md).
