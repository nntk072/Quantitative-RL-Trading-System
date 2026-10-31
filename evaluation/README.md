# Evaluation

`evaluation/` applies a saved decision provider to chronological data and
turns transitions into trade, equity, metric, plot, and report evidence. It is
backend-neutral at the rollout boundary and must use compatible observation,
action, execution, and account semantics.

| Area | Responsibility |
|---|---|
| `rollout/` | Run policy decisions against a supplied environment/provider. |
| `metrics/` | Compute trade and account outcome measures. |
| `plotting/`, `reporting/` | Render equity, trade, and summary outputs. |
| `metrics/trade_setup_policy.py`, `reporting/trade_setup_plots.py` | Analyze and plot setup choice and execution behavior; legacy `thesis_*` module paths re-export these APIs. |
| `reanalysis/` | Recompute analysis from preserved run evidence. |
| `cli.py` | Evaluation command entry point. |

Evaluation should reconcile from trade/equity ledgers. It reports observed
historical outcomes, not a guarantee of future performance. Previously
exposed periods must not be represented as untouched confirmation.

See the [evaluation guide](../docs/modules/evaluation.md),
[evaluation flow](../docs/architecture/data_flow.md), and
[validation protocol](../docs/thesis/validation_protocol.md).

## Replay and reporting path

The rollout layer obtains an action from a backend-neutral decision provider
and advances the configured environment. It records account and trade events;
metrics, diagnostic breakdowns, plots, and Markdown/JSON exports should be
derived from these same ledgers. Reanalysis reads preserved artifacts and
recomputes selected views without retraining the policy.

Chart inputs and shared overlay models are described in the local
[plotting guide](plotting/README.md).

Evaluation configuration must identify the data interval, observation/action
schema, tick or bar execution mode, costs, and account guardrails. If any of
these differ from training, declare the difference and its purpose. A summary
metric is not a substitute for examining trade exits, exposure, cost, and
drawdown paths. Focused tests live in `tests/unit/evaluation/`; backtest and
end-to-end reporting tests are under `tests/integration/`.
