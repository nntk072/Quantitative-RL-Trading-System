# Live and paper trading implementation status

The root entrypoints are `live_trading_rl.py` (RL checkpoint),
`live_trading.py` (rule-based multi-symbol strategies), and
`demo_trading.py` (single-symbol demo). The latter two forward to
`integrations/mt5/cli/`. All default to paper trading; real orders require the
literal value `false`. Read [deployment](DEPLOYMENT.md) before interacting
with a broker.

`live_trading_rl.py` reads `RL_MODEL_PATH` or `--model`, loads its saved
configuration when available, and connects to MT5 through
`integrations.mt5/domain/data_sources/mt5_data.py` and `MT5Trader`. It expects a
Windows MT5 terminal and must be executed on a supported terminal host,
not on a generic Triton GPU node. Inspect the code and logs for initialization
errors, missing model files, market disconnections and symbol mismatches.
`live_trading.py` also uses `MT5_TERMINAL_PATH` and `STRATEGY_TYPE`. Both
rule-based root commands accept `--once` to run one cycle and exit.

The repository's FTMO-style backtest limits (`trading/risk/guardrails.py`)
and live sizing configuration (`live_risk_overrides`) are separate systems.
No live/broker risk equivalence or demonstrated profitability is asserted.
Paper-trading promotion criteria in [DEPLOYMENT.md](DEPLOYMENT.md) are a
process proposal, **not evidence of a completed trial or live authorization**.
