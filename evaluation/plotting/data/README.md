# Evaluation plotting data charts

This package renders market-data quality, EDA, signal, PO3/IFVG, and pre-RL
diagnostic charts from the supplied bars and feature frames. Its `defense`,
`exploration`, and `po3` modules keep those chart families together while
loading on demand.

## Public API

`evaluation.plotting.data` lazily exports the chart functions listed in its
`__all__`. The former `evaluation.plotting.defense_plots`, `data_plots`, and
`po3_plots` module paths remain as compatibility facades for existing callers.

## Invariants

- Plotting reads its supplied data and does not modify the source frames.
- Train/test boundaries and session masks remain explicit chart inputs; plots
  must not use held-out rows for train-only summaries.
- Missing data is shown as missing or empty; chart code does not fabricate
  events, prices, or feature values.
- Rendering and output paths continue to use the shared plotting helpers.
- PO3 EDA and static signal charts import one another only inside the functions
  that need them, keeping their package imports cycle-free.
