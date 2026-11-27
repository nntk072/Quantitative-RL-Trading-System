# Constrained RL

**Status:** Wave D draft
**Use this when:** You need to understand the PPO Lagrange callback and its relationship to hard account guardrails.

## Summary and use this when

The constrained PPO callback adjusts rewards seen by learning through a bounded Lagrange multiplier. It reads cost signals from environment info and updates the multiplier when completed episodes are available. Environment hard guardrails remain separate. A soft training objective cannot certify that a policy respects a hard limit.

- Start with the resolved configuration and the named input/output contracts.
- Follow one transition or fit path in source before interpreting a metric.
- Treat the linked notebook as a mechanics example using bundled synthetic data.

## Key terms

- [Risk budget](../../glossary.md)
- [PPO](../../glossary.md)
- [Episode](../../glossary.md)
- [Checkpoint](../../glossary.md)
- [Rollout](../../glossary.md)

## Explanation

### Decision or learning boundary

The constrained PPO callback adjusts rewards seen by learning through a bounded Lagrange multiplier. It reads cost signals from environment info and updates the multiplier when completed episodes are available. Environment hard guardrails remain separate. A soft training objective cannot certify that a policy respects a hard limit.

The five source-backed contracts below identify where this subject crosses a
package boundary. Read them together: a policy output has meaning only under
the environment, schema, and run identity that produced it.

### 1. Cost is normalized to maximum-loss units

The callback compares daily, maximum-loss, and enabled trailing incremental costs after scaling to configured maximum-loss units; breach flags impose at least one unit.

- Source: `learning/rl/callbacks.py::LagrangianRiskCallback._episode_cost` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/training/test_lagrangian_callback.py`.
- Practical check: Interpret episode_cost_budget in maximum-loss-equivalent units.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 2. Rewards are shaped during collection

The callback subtracts lambda times the cost from the rollout reward array and accumulates discounted episode cost. It validates vector batch lengths.

- Source: `learning/rl/callbacks.py::LagrangianRiskCallback._on_step` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/training/test_lagrangian_callback.py`.
- Practical check: Keep environment reward and shaped rollout reward distinct.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 3. Dual update waits for completed episodes

When completed costs exist, lambda becomes clip(lambda + learning_rate*(mean_cost-budget), 0, lambda_max). No completed episode means no dual update.

- Source: `learning/rl/callbacks.py::LagrangianRiskCallback._on_rollout_end` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/training/test_lagrangian_callback.py`.
- Practical check: Inspect completed_episodes and dual_updates together.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 4. Saved state guards resume compatibility

On callback training start, saved callback configuration must match current settings and saved lambda must lie inside configured bounds.

- Source: `learning/rl/callbacks.py::LagrangianRiskCallback._on_training_start` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/training/test_lagrangian_callback.py::test_q5_callback_restores_checkpoint_state_and_rejects_config_drift`.
- Practical check: Do not silently change cost scales across a resumed run.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 5. The environment still owns hard breaches

The environment step checks and records account constraints. Callback shaping cannot weaken its breach latch or create permission to exceed hard floors.

- Source: `simulation/environment/episode/constraints.py` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/simulation/test_environment/test_risk_alignment.py`.
- Practical check: Inspect both hard constraint outcomes and learning diagnostics.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

## Worked example

The notebook applies the exact bounded dual-update equation to a fixed sequence of completed episode costs. It shows a zero-cost rollout with no update separately.

Open the [Tier A notebook](examples/constrained-rl.ipynb). It runs on CPU using
only deterministic values bundled in the cell. It neither trains nor evaluates
a market policy.

```{toctree}
:hidden:

examples/constrained-rl
```

The [compact contract reference](../../reference/subjects/constrained-rl.md) records
the exact source-facing obligations for maintainers.

## Tasks

- Read hard loss limits and the callback budget in the resolved config.
- Check the cost units before comparing episode traces.
- Inspect breach flags even if shaped reward appears favorable.
- On resume compare saved callback configuration and multiplier bounds.

## Contract

| Boundary | Required behavior | Source |
|---|---|---|
| Cost is normalized to maximum-loss units | The callback compares daily, maximum-loss, and enabled trailing incremental costs after scaling to configured maximum-loss units; breach flags impose at least one unit. | `learning/rl/callbacks.py::LagrangianRiskCallback._episode_cost` |
| Rewards are shaped during collection | The callback subtracts lambda times the cost from the rollout reward array and accumulates discounted episode cost. | `learning/rl/callbacks.py::LagrangianRiskCallback._on_step` |
| Dual update waits for completed episodes | When completed costs exist, lambda becomes clip(lambda + learning_rate*(mean_cost-budget), 0, lambda_max). | `learning/rl/callbacks.py::LagrangianRiskCallback._on_rollout_end` |
| Saved state guards resume compatibility | On resume, saved callback configuration must match current settings and saved lambda must lie inside configured bounds. | `learning/rl/callbacks.py::LagrangianRiskCallback._on_training_start` |
| The environment still owns hard breaches | The environment step checks and records account constraints. | `simulation/environment/episode/constraints.py` |

## Verify

For this subject, inspect the focused tests before changing a contract:

- `tests/unit/training/test_lagrangian_callback.py` — cost is normalized to maximum-loss units.
- `tests/unit/training/test_lagrangian_callback.py` — rewards are shaped during collection.
- `tests/unit/training/test_lagrangian_callback.py` — dual update waits for completed episodes.
- `tests/unit/training/test_lagrangian_callback.py::test_q5_callback_restores_checkpoint_state_and_rejects_config_drift` — saved callback state rejects configuration drift.
- `tests/unit/simulation/test_environment/test_risk_alignment.py` — the environment still owns hard breaches.

The notebook is a deterministic teaching check. A repository test is a
software check. Neither is an out-of-sample result or a claim of economic
performance. Keep those evidence categories separate in reports.

## Limits and common mistakes

- A Lagrange update is not a safety guarantee.
- The toy costs are fixed inputs, not simulator measurements.
- Hard breach and no-trade outcomes remain reportable results.

- Do not use a smoke run as evidence of a strategy effect.
- Do not select a model or threshold using the exposed 2026 reporting interval.
- Preserve invalid, negative, breached, no-trade, and incomplete outcomes.

## Change checklist

Before changing this behavior:

1. Read hard loss limits and the callback budget in the resolved config.
2. Check the cost units before comparing episode traces.
3. Inspect breach flags even if shaped reward appears favorable.
4. On resume compare saved callback configuration and multiplier bounds.
5. Update the relevant schema, caller, fixture, and focused test if the
   behavior or serialized meaning changes.
6. Record the source revision, resolved config, data identity, and artifact
   digest for any run used in a research claim.

## Review procedure

Read one source path and its directly connected test at the pinned revision.
Recheck any claim against the active checkout before relying on current behavior.
Use the notebook to inspect a tiny boundary case, then inspect actual run
artifacts separately if the question is about a trained policy. Record
mismatches rather than silently adapting a saved checkpoint or report.

## Maintainer note

- Verified source baseline: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Current dirty-source-only behavior is unverified by this page.
- Owner: `ml_engineer`.
- Notebook tier: A; synthetic, deterministic CPU example.
