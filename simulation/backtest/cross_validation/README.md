# Backtest engine comparison utilities

This directory contains a bounded comparison harness for a crossover strategy
using Backtrader and the project's custom event engine. It loads an input frame,
constructs delayed signals, runs both engines, and compares their reported
results.

The directory name is historical: these helpers do not implement the
project's purged walk-forward split protocol. Use `market_data/splits/` and the
validation documentation for dataset partitioning. The comparison harness is
not a general proof that the engines have equivalent fill assumptions.

Focused tests, when present, are under `tests/integration/backtest/`. See the
[event-driven backtest guide](../README.md).
