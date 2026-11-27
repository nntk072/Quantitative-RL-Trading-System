# Shared plotting helpers

This package holds rendering constants and output, time-series transforms,
chart indicators, and order-chart level geometry reused by static and
interactive plotting families.

## Public API

`evaluation.plotting.shared` lazily exports the stable helper names listed in
`__all__`. The former `plot_rendering`, `plot_series`, `chart_indicators`, and
`chart_levels` module paths remain compatibility facades.

## Import relationships

- Rendering and series helpers depend only on plotting libraries and values.
- Indicator helpers import overlay functions locally to avoid coupling the
  shared package import to overlay rendering.
- Level helpers depend on candle-quality and order-level geometry.
- Plot families import the owning shared modules directly; shared helpers do
  not import plot-family packages.
