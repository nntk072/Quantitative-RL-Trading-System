# Local session account transition trace

This packet uses short, controlled action sequences over supplied US100
training M1 bars from two distinct date-derived session IDs. It compares
environment and event-backtest fills, realized PnL, session-start balance
resets, daily-loss blocking, and final account state. It is not a learned-policy
replay or an economic performance estimate.

Both engines reset their session-start balance from their own prior-session
close PnL. The bar fallback and tick-required traces use the same next-market-
bar open time and quote contract across engines. The tick-required report uses
the same TickBook and 30 ms randomized latency in both engines. Each report
preserves exact event comparisons and the reset checks; neither is a learned-
policy replay.

The daily-loss trace sets a controlled $1 hard daily limit, attempts another
entry after a first-session loss crosses that limit, and checks that both
engines latch account failure across the remainder of the evaluation.

The max-loss trace sets a controlled $1 account-loss limit and runs the
environment episodically. Both engines record the max-loss breach and make no
same-session or later-session opens; the environment terminates at the breach.

Local session labels and date-derived IDs are used as supplied. No external
clock, provider, or calendar claim is made.

## Files

- `session_account_transition.json`: controlled bar-fallback trace.
- `session_tick_account_transition.json`: controlled TickBook trace when
  generated with `--ticks-csv`.
- `daily_breach_full_evaluation_failure.json`: controlled daily-breach latch
  trace generated with `--scenario both --ticks-csv`.
- `session_tick_max_loss_terminal.json`: controlled episodic max-loss
  termination and rollout-wide open latch when generated with `--scenario all --ticks-csv`.
- `session_*_verification.json`: independently recomputed trace and input/source
  byte verification.
- `OUTPUT_SHA256SUMS`: packet and generator hashes.

## Reproduction

```bash
.venv/bin/python scripts/research/analysis/evaluation/compare_simulator_local_session_account_trace.py
.venv/bin/python scripts/research/analysis/evaluation/compare_simulator_local_session_account_trace.py --scenario both --ticks-csv data/training/US100.cash_202412300105_202610162349.csv
.venv/bin/python scripts/research/analysis/evaluation/compare_simulator_local_session_account_trace.py --scenario all --ticks-csv data/training/US100.cash_202412300105_202610162349.csv
.venv/bin/python scripts/research/analysis/evaluation/verify_simulator_local_session_account_trace.py evidence/research/simulator_execution_parity/local_session_account_transition/session_tick_account_transition.json evidence/research/simulator_execution_parity/local_session_account_transition/daily_breach_full_evaluation_failure.json evidence/research/simulator_execution_parity/local_session_account_transition/session_tick_max_loss_terminal.json
```
