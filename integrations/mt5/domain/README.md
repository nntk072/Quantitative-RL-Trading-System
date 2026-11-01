# MetaTrader 5 domain implementation

`integrations/mt5/domain/` implements the adapter contracts for MetaTrader
data, order handling, risk checks, signal values, and vendor-backed strategies.
The `trader.py` module translates broker position state and requests; strategy
modules derive signals from supplied market data.

The implementation depends on the MetaTrader integration and should not be
used as the broker-neutral trading domain. Keep risk and execution assumptions
explicit, and test vendor field mapping separately from generic account and
order semantics. Focused checks are in `tests/unit/integrations/`.
