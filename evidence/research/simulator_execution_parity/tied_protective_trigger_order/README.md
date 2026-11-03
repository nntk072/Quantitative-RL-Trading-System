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

Observed result: `1 passed in 0.37s`. The paired quote-wait-gap test and this
case also pass together (`2 passed in 0.35s`) on `gpuarm2`, job `21367992`,
2026-11-03. No new Slurm job or step was created.

## Source identities at verification

- Test: `a9fbb1f54d3fbae3e73c28da82752eb55bc3201ce1b1afa99a126f9643b208c1`
- Environment protective runtime:
  `415fdabf0b2dadd5572221cc8cc75cac13ee5c864f76af5059a36c4f463b4d27`
- Backtest protective runtime:
  `7d873860ed80dc251e87fdede298eb189cb21801b8f1d88c4c88941dec1faf48`
- TickBook execution resolver:
  `50250798b0db1a8a20e5b006705bff40b40861860e538493c407ae28d6d41f83`
