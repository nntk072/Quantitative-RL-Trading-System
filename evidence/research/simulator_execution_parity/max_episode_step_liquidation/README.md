# Episode step-limit liquidation parity

## Question

When `max_episode_steps` truncates an environment episode while a position is
open, does the environment realize the position at the same terminal bar and
quote as an event-driven backtest run on that same effective window?

## Method and result

The paired integration case compares natural data end and a four-step episode
limit at zero and 30 ms randomized fill latency. The backtest receives the
equivalent terminal-bar slice. All four cases pass: terminal fill timestamp,
price, PnL, balance, and equity agree between the environment and backtest.
The touched-source Ruff format and lint checks pass; the adjacent risk-lifecycle,
repeated-payout, and year-survival suites pass 40 tests.

The environment records `reason=max_episode_steps` for the explicit cutoff;
the backtest's truncated input reports its existing natural `data_end` reason.
Those reason labels describe different causes even though the matched terminal
fill and account result agree.

## Scope limits

This closes terminal liquidation for the tested episode step limit. It does
not establish arbitrary early-reset semantics, checkpoint/replay determinism,
open-position mark-to-market parity at intermediate steps, overnight tails,
nonzero financing, or full action-to-fill and account-report reconciliation.
The broader Stage E acceptance gate remains open.

## Reproduction

From the repository root on the existing ARM64/GH200 environment:

```bash
.venv/bin/python -m pytest tests/integration/backtest/test_risk_lifecycle_characterization.py::test_terminal_liquidation_matches_environment_and_backtest -q
.venv/bin/python -m pytest tests/integration/backtest/test_risk_lifecycle_characterization.py tests/integration/backtest/test_repeated_payout_backtest.py tests/unit/simulation/test_environment/test_year_episode_survival.py -q
```

Exact command output is in `run_output.txt`; source hashes are in
`SOURCE_SHA256SUMS`.
