# Position stop lifecycle characterization

This packet records 26 shared stop-helper unit cases and 16 paired
`TradingEnv` / `run_backtest` lifecycle cases in the existing GH200 allocation;
all 42 passed. Environment and backtest now call the same
`confirmed_swing_trailing_stop_price` calculation for directional stop
placement, monotonic tightening, and protective-side checks. The paired cases
compare buffered breakeven movement, confirmed-swing trailing updates,
next-bar effectivity, protective-close PnL/equity, daily-loss reset, rollout
max-loss lockout, and scheduled session close.

These are controlled synthetic cases. They do not establish historical-policy
behavior, broker parity, financing treatment, checkpoint/replay determinism,
or complete account and cashflow acceptance. The broader Stage E gate remains
open.

Reproduce inside an existing ARM64/GH200 allocation:

```bash
.venv/bin/python -m pytest -q \
  tests/unit/trading/test_stop_management.py \
  tests/integration/backtest/test_risk_lifecycle_characterization.py
```

Exact output, run context, and source hashes are preserved in this packet.
