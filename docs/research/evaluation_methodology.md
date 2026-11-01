# Evaluation methodology

Evaluation replays a frozen policy on a declared period and records what the
simulated account and policy did. It is distinct from fitting model parameters.
The `evaluation/` package owns rollout, metrics, reanalysis, reporting, and
plots; simulation owns environment transitions and event-driven backtesting.

## Evaluation record

For each result, retain:

- checkpoint, source, resolved configuration, dataset, feature/cache, and
  evaluation-manifest identities;
- period boundaries and their training, selection, exploratory, or final role;
- observation/action schema, policy action mode, random seed, and environment
  settings;
- costs, fill source, latency assumptions, and risk rules;
- equity and drawdown paths, fill/trade ledger, risk outcomes, metrics, and
  report figures.

The report should explain missing artifacts as missing requirements, not imply
that an unavailable plot or metric was produced. It should include inactive and
zero-trade behavior together with trading outcomes.

## Choose the replay path

Use a `TradingEnv` rollout to evaluate a provider through the environment
transition contract. Use the event-driven backtest to replay orders, fills,
positions, and account rules as a backtest result. A training smoke or
environment throughput benchmark is not a full backtest. Investigate
differences between the two paths before comparing their results.

## Comparison and interpretation

Matched comparisons should share the dataset and split, action meaning, reward
and risk rules, costs, execution assumptions, training budget, seed, starting
capital, and evaluation window. Use timestamp-paired comparison intervals when
the matched-comparison contract supports them. Include trade counts,
profitability, drawdown, survival, execution costs, and action/entry/exit
behavior; a summary metric alone is insufficient to explain a policy result.

Keep measured outcomes separate from causal interpretation. See the
[validation protocol](validation_protocol.md) for period roles and the
[limitations](limitations.md) for interpretation boundaries.
