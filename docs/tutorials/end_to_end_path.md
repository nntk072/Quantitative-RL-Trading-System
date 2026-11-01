# End-to-end learning path

This sequence connects the runnable examples into one bounded walk through the
system. All core notebooks use synthetic/bundled data and CPU-scale examples;
no full training campaign is required.

```text
timestamped bars
  → causal feature window
  → observation and validity masks
  → policy action / trade intent
  → eligibility, risk and execution checks
  → account transition and reward
  → metrics, artifacts and evidence limits
```

## Walk the path

1. [Market data](../learn/tutorials/01_market_data.ipynb) checks bar indexes,
   OHLC values, and data shape.
2. [Causal features](../learn/tutorials/02_causal_features.ipynb) demonstrates
   when a completed higher-timeframe value becomes visible.
3. [Trading and risk](../learn/tutorials/03_trading_and_risk.ipynb) plots a
   proposed entry with stop and target references.
4. [Environment step](../learn/tutorials/04_environment.ipynb) builds the real
   `TradingEnv` from a small deterministic synthetic dataset, submits a
   baseline action, and inspects the accepted position and diagnostics.
5. [Evaluation](../learn/tutorials/05_evaluation.ipynb) calculates an equity
   path and drawdown from a bounded synthetic series.
6. [Deterministic environment trace](../reproduce/environment_trace.ipynb)
   asserts an expected fill, stop, account, and reward transition. It is R2
   software-behavior evidence, not a policy-performance result.
7. [Run artifact guide](../reproduce/result_registry.md) explains the
   checkpoint, manifest, input identity, and evidence level required before a
   research claim.

## Interpret the worked decision

In the environment notebook, the action is a request. The environment first
advances market state and processes existing protective conditions; it then
decodes eligibility, resolves the entry/stop/target geometry, applies risk,
and records the fill. The next observation, reward, and `info` diagnostics
describe the result. A selected action may be rejected in other states; never
equate action frequency with fill frequency.

The synthetic fixture makes expected behavior reproducible, but its prices do
not model real spreads, market impact, broker latency, or future returns. Use
the [execution costs concept](../concepts/execution_and_costs.md) and
[reproducibility guide](../concepts/reproducibility.md) when moving from
software validation to a research claim.
