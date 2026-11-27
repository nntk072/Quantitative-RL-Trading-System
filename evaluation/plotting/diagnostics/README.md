# Evaluation plotting diagnostics

This package renders trade-level diagnostics, PnL distributions, and policy
decision-diversity charts from evaluation tables and reports.

## Public API

The package exposes trade, distribution, and diversity chart functions through
`evaluation.plotting.diagnostics.__all__`. The former root modules
`trade_plots`, `distribution_plots`, and `diversity` remain compatibility
facades.

## Invariants

- Chart functions consume evaluation records and do not change those records.
- Missing or empty inputs remain visible as empty chart states; chart code does
  not synthesize trades or outcomes.
- Distribution and diversity charts preserve the supplied metrics, groups,
  and labels.
- Rendering continues to use the shared plotting style and save helpers where
  applicable.
