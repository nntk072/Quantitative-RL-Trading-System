# Cross-validation data utilities

## Purpose

Load tabular market data into the Backtrader feed format used by the
cross-validation harness.

## Public API

`simulation.backtest.cross_validation.utils.data_loader` provides
`load_data_from_csv` and `download_data_from_yahoo`.

## Invariants

- CSV dates are parsed from the declared date or datetime column, or from an
  already datetime-indexed frame.
- Feed columns retain the OHLCV ordering expected by Backtrader.
- Yahoo downloads are explicit calls; importing the package does not access
  the network.
