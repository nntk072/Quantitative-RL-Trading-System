# Tied protective-trigger ordering

## Question

When two source rows share one millisecond timestamp and one crosses the stop
while the next crosses the target, do both engines apply the same deterministic
TickBook source-order tie-break?

## Controlled case

- A long position has structural stop and target levels.
- Two quotes share the same millisecond timestamp and preserve input source
  order in the production `TickBook`.
- The first quote's bid is 95.0 and crosses the stop; the second quote's bid is
  110.0 and crosses the target.
- Both the training environment and event-driven backtest close at the first
  source-ordered quote, classify the exit as `structure_sl`, and reconcile the
  final account balance.

This verifies deterministic implementation behavior only. Stable source order
is not evidence of true sub-millisecond market chronology, and the synthetic
prices do not represent an observed trade.

## Reproduction

From the repository root, inside the existing GH200 allocation:

```bash
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/integration/backtest/test_account_transition_parity.py::test_environment_and_backtest_use_first_source_order_for_tied_stop_target_ticks \
  -q
```

Verified against current source in the existing allocation `21405414` on
`gpuarm1`: the tied-trigger and paired quote-wait-gap tests pass together
(`2 passed in 0.36s`). Log:
`/scratch/work/nguyenl37/agent_plans/Quantitative-RL-Trading-System/tied_protective_trigger_order_current.log`.
No new Slurm job or step was created.

## Source identities at verification

- Test: `a9fbb1f54d3fbae3e73c28da82752eb55bc3201ce1b1afa99a126f9643b208c1`
- Environment protective runtime:
  `0fc74436816d7bc7a2db7b30615b65b8c536f331bb15911362d0fff1dff0747d`
- Backtest protective runtime:
  `fb87b6e84e3393191da1c392f0c1b4d3636ad33a2f971d087f433f3b2fc670e6`
- TickBook execution resolver:
  `6973db5a21d0adeebfd7f44c808525efc77dfdbb61333170219c37c850f51a31`
