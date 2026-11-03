# Controlled action and account parity

The paired environment/backtest characterization module passed all 23
parametrized cases in the existing GH200 allocation. Cases cover realized/open
account transitions across starting balances and daily-loss bases; long/short
tick execution across fail-closed mode, slippage, and randomized latency;
pending-entry action consumption; quote-wait failure; deterministic source-order
handling of tied protective triggers; delayed-entry session boundary; risk-cap
sizing; and insufficient-margin rejection without account mutation.

The suite uses controlled traces and current code. It does not close the full
simulator acceptance gate: limit-price/TTL order behavior is unsupported by the
current action path, tied tick chronology is only a stable source-order rule,
and the broader risk, accounting, checkpoint/replay, and training/live parity
matrix still has open cases.

Reproduce inside an existing ARM64/GH200 allocation:

```bash
.venv/bin/python -m pytest -q \
  tests/integration/backtest/test_account_transition_parity.py
```

Exact command output is preserved in `pytest_output.txt`; source identity and
run scope are in `run_metadata.json`.
