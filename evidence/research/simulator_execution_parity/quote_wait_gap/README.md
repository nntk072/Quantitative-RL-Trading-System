# Fail-closed quote-wait gap

## Question

Do the training environment and event-driven backtest refuse the same entry
when the first executable tick arrives outside the configured quote-wait
bound, without substituting candle prices?

## Controlled case

- Six UTC M1 bars have constant 100.0 OHLC center, with a 1.0 high/low range.
- A single complete TickBook quote arrives 2 ms after the scheduled fill.
- Both engines require tick execution and use `max_tick_quote_wait_ms=1`.
- The environment raises `TickExecutionUnavailable` with `no executable quote
  within 1ms`.
- The event backtest raises `TickExecutionUnavailable` with `no executable tick
  within 1ms`.
- Both fail closed; no candle-priced fill or completed trade is returned.

The difference in exception wording reflects the caller boundary. The failure
type and execution policy match. This is a synthetic contract characterization,
not an empirical quote-staleness estimate or a historical-policy replay.

## Reproduction

From the repository root, inside the existing GH200 allocation:

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/integration/backtest/test_account_transition_parity.py::test_environment_and_backtest_both_fail_closed_on_quote_wait_gap \
  -q
```

Observed result: `1 passed in 0.39s` on `gpuarm2`, job `21367992`, 2026-11-03.
No new Slurm job or step was created.

## Source identities at verification

- Test: `a9fbb1f54d3fbae3e73c28da82752eb55bc3201ce1b1afa99a126f9643b208c1`
- Environment quote resolver: `42c0b3beba520baf83c6b3e424736b3adc14aa847f3c6e6f0b5aaf77e999651f`
- Backtest quote resolver: `7cb506ad492762f3103439e9038e2bbd4f3c47eee6a6f5bb15b8f55c38074aa9`
- TickBook execution resolver: `50250798b0db1a8a20e5b006705bff40b40861860e538493c407ae28d6d41f83`
