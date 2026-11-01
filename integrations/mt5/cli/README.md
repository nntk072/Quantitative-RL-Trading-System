# MetaTrader 5 command-line applications

`integrations/mt5/cli/` contains single-symbol and multi-symbol application
entrypoints. They load runtime configuration, construct the corresponding
robot and strategies, and start either a one-shot cycle or the configured
scheduler.

These entrypoints can place live orders when connected to a configured
MetaTrader terminal. Review account, symbol, risk, and scheduling settings
before use. Keep command construction here and broker-specific operations in
the MT5 adapters. Focused checks are in `tests/unit/integrations/` and
`tests/integration/`.
