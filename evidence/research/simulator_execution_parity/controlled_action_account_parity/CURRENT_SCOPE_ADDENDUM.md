# Current scope correction

This packet preserves its 23-case historical test scope and README unchanged.
It predates the learned market/limit implementation and does not test its
price, TTL, fill, or cancellation rules. Those current paths are traced in
`../learned_market_limit_execution_path/` and tested separately by
`tests/integration/backtest/test_agent_selected_entry_execution.py`.

The original limits on tied-tick chronology, broader account/report parity,
checkpoint replay, and training/live parity remain applicable.
