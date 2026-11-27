# Evaluation plotting performance charts

This package renders equity, drawdown, daily P&L, return-distribution, and
baseline-comparison charts from supplied evaluation series and trade records.

## Public API

`evaluation.plotting.performance` exports the chart functions listed in its
`__all__`. The `equity.py` and `comparison.py` compatibility modules remain at
their former paths. The former `performance.py` import path is now this package
facade, so its chart imports continue to work.

## Invariants

- Chart functions consume the supplied evaluation records and do not mutate
  them or change trading decisions, fills, or risk limits.
- Daily summaries use the shared session and date-series helpers so chart
  boundaries remain consistent with the recorded evaluation data.
- Missing or empty inputs are rendered as empty states instead of fabricated
  observations.
