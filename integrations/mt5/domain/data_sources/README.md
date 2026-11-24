# MT5 market-data sources

## Purpose

Adapt MetaTrader 5 terminal rate queries to the integration's `TradingData`
interface.

## Public API

`integrations.mt5.domain.data_sources.mt5_data.MT5Data` fetches recent rates
for a configured symbol and timeframe and exposes the configured symbol.

## Invariants

- MT5 calls stay inside this integration adapter; domain consumers use the
  `TradingData` interface.
- Terminal epoch timestamps are converted from seconds to datetimes.
- An empty terminal response remains an empty frame.
