# MT5 domain strategies

## Purpose

Generate broker-neutral trading signals from data supplied through the MT5
integration's `TradingData` interface.

## Public API

`integrations.mt5.domain.strategies` exports `CrossOverStrategy`,
`SMCStrategy`, `TrendBreakoutStrategy`, and `CombinedStrategy`.

## Invariants

- Strategy evaluation returns a symbol and domain `Signal`; execution belongs
  to the application layer.
- Strategies obtain market data through `TradingData`, not directly through
  the MT5 terminal API.
- `CombinedStrategy` aggregates the configured component strategies using its
  `require_all` or majority rule.
