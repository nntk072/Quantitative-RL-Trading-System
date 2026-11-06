# Current scope correction

This packet preserves its historical test scope and README unchanged. It
predates the candidate-mask backtest extension and learned market/limit entry
path, so it does not test cross-engine mask parity or limit-order lifecycle.
Current coverage is in `../setup_mask_engine_boundary/`,
`../learned_market_limit_execution_path/`, and
`tests/integration/backtest/test_agent_selected_entry_execution.py`.

The original limits on authoritative same-timestamp chronology, historical PPO
action linkage, and full Stage E parity remain applicable.
