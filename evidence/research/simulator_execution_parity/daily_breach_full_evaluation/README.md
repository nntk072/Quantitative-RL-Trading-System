# Daily-loss breach fails the full evaluation

## Result

The paired environment/backtest characterization passes. Both simulators start
with $100,000, breach the $0.50 synthetic daily-loss threshold in session 0,
record one `daily_loss` breach, and receive an always-long policy through a
later session. Each records only its pre-breach opening and does not reopen in
session 1. This verifies the user-selected full-evaluation failure behavior for
this controlled path.

## Reproduction

Run inside the compatible existing GH200 allocation:

```bash
.venv/bin/ruff format --check tests/integration/backtest/test_risk_lifecycle_characterization.py
.venv/bin/ruff check tests/integration/backtest/test_risk_lifecycle_characterization.py
.venv/bin/python -m pytest tests/integration/backtest/test_risk_lifecycle_characterization.py::test_daily_loss_breach_fails_full_evaluation -q
```

Observed result: formatting and lint passed; `1 passed in 1.41s` on 2026-11-04
in Slurm allocation `21405414`. The output is preserved in `run_output.txt`.
`SOURCE_SHA256SUMS` identifies the simulator, shared guardrail, and test files
used by this characterization.

## Claim limits

This is a deterministic synthetic integration test, not a market-path result or
a complete simulator/accounting parity proof. It checks the daily-breach latch
across one supplied session transition. The remaining Stage E lifecycle,
accounting, execution, and report-semantic gates stay open.
