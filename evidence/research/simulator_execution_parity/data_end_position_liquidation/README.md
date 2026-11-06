# Open-position liquidation at evaluation data end

## Finding and correction

A controlled source-level comparison found that `run_backtest` realized an open
position at the terminal bar close, while `TradingEnv` left the position open
when its final policy bar truncated the data split. The environment now closes
any remaining position before recording terminal account and reward values. A
configured 0–30 ms tick fill uses the same event key (`bar_fill` plus terminal
fill timestamp) and seed in both engines.

## Evidence

The paired synthetic integration test compares zero latency and 30 ms
randomized latency. Both engines reach data end with no open position and match
terminal fill time, price, PnL, balance, and equity. The randomized case also
matches the sampled latency. Both test cases pass. The broader adjacent
risk-lifecycle, repeated-payout, and year-survival suites pass 38/38; touched
path Ruff format and lint pass. Exact command output is in `run_output.txt`.
The source identities are in `SOURCE_SHA256SUMS`.

## Reproduction

Run on the compatible existing GH200 allocation:

```bash
.venv/bin/ruff format --check simulation/environment/step_accounting_runtime.py simulation/backtest/protective_events.py tests/integration/backtest/test_risk_lifecycle_characterization.py
.venv/bin/ruff check simulation/environment/step_accounting_runtime.py simulation/backtest/protective_events.py tests/integration/backtest/test_risk_lifecycle_characterization.py
.venv/bin/python -m pytest tests/integration/backtest/test_risk_lifecycle_characterization.py::test_data_end_liquidates_open_position_in_environment_and_backtest -q
.venv/bin/python -m pytest tests/integration/backtest/test_risk_lifecycle_characterization.py tests/integration/backtest/test_repeated_payout_backtest.py tests/unit/simulation/test_environment/test_year_episode_survival.py -q
```

## Claim limits

This closes terminal liquidation for a completed data split when a position is
still open on its final policy bar, including the configured randomized-tick
latency path. It is a controlled synthetic parity result. It does not close
arbitrary `max_episode_steps` truncation, overnight-held post-NY data tails,
full account/report reconciliation, or the broader simulator-parity gate.
