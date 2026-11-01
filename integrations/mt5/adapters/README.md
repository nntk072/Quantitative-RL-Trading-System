# MetaTrader 5 adapters

These interfaces define the data, strategy, and trader operations expected by
the MetaTrader 5 runtime. `data.py` supplies the market-data contract;
`strategy.py` defines the signal-producing strategy interface; `trader.py`
defines position and order operations consumed by robot implementations.

This package is broker-specific. Convert MetaTrader timestamps, symbols,
position fields, and vendor result codes at this boundary; keep generic order,
risk, and account meaning in `trading/`. Focused checks are in
`tests/unit/integrations/`.
