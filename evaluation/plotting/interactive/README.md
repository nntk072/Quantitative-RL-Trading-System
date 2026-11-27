# Evaluation plotting interactive charts

This package renders interactive Plotly views of evaluation metrics, trades,
orders, and PO3/IFVG chart context.

## Public API

`evaluation.plotting.interactive` exports the chart functions listed in its
`__all__`. The former `evaluation.plotting.interactive_*` modules and
`evaluation.plotting.plots_interactive` facade remain available for existing
callers.

## Invariants

- Plotly remains an optional dependency; importing plotting code must succeed
  without it, and chart calls fail with a clear dependency message.
- Charts consume supplied ledgers and frames without mutating them or changing
  evaluation, trading, or risk decisions.
- Output helpers create parent directories and write the requested HTML path.
