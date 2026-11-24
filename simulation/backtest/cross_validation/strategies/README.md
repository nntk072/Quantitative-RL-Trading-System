# Cross-validation strategies

## Purpose

Backtrader strategy implementations used by the backtest cross-validation
harness to compare reference strategies and replay fixed signals.

## Public API

`simulation.backtest.cross_validation.strategies` exports
`CrossOverStrategy`, `EMAMACDStrategy`, `MACDStrategy`, and
`SignalFollowingStrategy`.

## Invariants

- Strategies emit or execute decisions from the data feed's current and past
  bars only.
- `SignalFollowingStrategy` consumes the caller-provided action series in bar
  order; it does not generate replacement signals.
- Strategy classes model Backtrader orders and do not submit broker orders.
