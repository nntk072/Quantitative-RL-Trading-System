# MetaTrader 5 robots

The robot classes connect strategy decisions to MetaTrader position sizing,
risk checks, and order operations. There are single-symbol, multi-symbol, and
RL-backed paths. The robot lifecycle is an integration concern; the shared
trade, risk, and order meanings remain defined by `trading/` contracts.

These paths can send live orders. Keep safety gates and broker responses
observable, and preserve symbol-specific sizing behavior. Focused checks are in
`tests/unit/integrations/` and the integration suite.
