# Validation protocol

An evaluation result is interpretable only when its data role, model identity,
action meaning, execution assumptions, and selection history are explicit.
This protocol applies to training, model selection, exploratory analysis, and
final reporting.

## Period roles

| Role | Permitted use |
|---|---|
| Training | Fit policy parameters and transformations that are declared train-fitted. |
| Validation or walk-forward folds | Select configurations under a predeclared procedure. Purge outcome overlap and apply the configured embargo. |
| Exposed exploratory period | Diagnose or develop after prior inspection. It cannot support a fresh confirmatory claim. |
| Locked final period | Final reporting only while it remains uninspected and unused for model or analysis decisions. |

Assign period roles before interpreting outcomes. Re-running an exposed period
does not restore its status as untouched. Record prior exposure, selection
permissions, and period boundaries in the experiment and evaluation manifests.
Do not change a locked period as an informal way to recover a holdout.

## Data and model controls

- Build features causally: a decision at time *t* may use only information
  available by *t*. Higher-timeframe values become available only after their
  source bars close.
- Fit normalization and other learned preprocessing on training data only.
  Reuse the last training-fitted state for later periods.
- Keep bars in the feature timeline. Session eligibility is a mask or input,
  not a reason to delete observations.
- Match the comparison's data, split, action schema, reward, risk settings,
  costs, execution model, training budget, random seeds, and evaluation window.
  Document every difference that could affect outcomes.
- Verify dataset, source, resolved configuration, cache, and checkpoint
  identities from manifests before comparing runs.

## Evaluation and claims

Declare whether a result comes from a `TradingEnv` rollout or the
event-driven backtest. They answer related but different questions and their
outputs must not be treated as interchangeable. State the action mode and seed,
execution and fill assumptions, risk termination rules, and report interval.

Report account survival and breaches, equity and drawdown, realized trades,
costs, action behavior, and meaningful inactive or zero-trade outcomes. Include
uncertainty and matched comparisons when making claims beyond description.
Separate the measured result from possible explanations; a single interval,
seed, or simulator configuration does not establish generalization or live
profitability.

For the current period exposure and research-specific gate, see the
[research execution plan](../operations/research_execution_plan.md). For the
implementation boundary between environment and backtest, see the
[simulation guide](../modules/simulation.md) and
[evaluation guide](../modules/evaluation.md).
