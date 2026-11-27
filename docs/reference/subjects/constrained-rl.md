# Constrained RL contract

This page records the subject-specific contract at source revision
`c0d982f94ab9df8b2a9ddd013d2ae9a562573529`. The generated API pages describe callable signatures;
the entries below record cross-package meaning and validation obligations.

## Contract table

| Contract | Exact obligation | Source and focused test |
|---|---|---|
| Cost is normalized to maximum-loss units | The callback compares daily, maximum-loss, and enabled trailing incremental costs after scaling to configured maximum-loss units; breach flags impose at least one unit. | `learning/rl/callbacks.py::LagrangianRiskCallback._episode_cost`; `tests/unit/training/test_lagrangian_callback.py` |
| Rewards are shaped during collection | The callback subtracts lambda times the cost from the rollout reward array and accumulates discounted episode cost. It validates vector batch lengths. | `learning/rl/callbacks.py::LagrangianRiskCallback._on_step`; `tests/unit/training/test_lagrangian_callback.py` |
| Dual update waits for completed episodes | When completed costs exist, lambda becomes clip(lambda + learning_rate*(mean_cost-budget), 0, lambda_max). No completed episode means no dual update. | `learning/rl/callbacks.py::LagrangianRiskCallback._on_rollout_end`; `tests/unit/training/test_lagrangian_callback.py` |
| Saved state guards resume compatibility | On callback training start, saved callback configuration must match current settings and saved lambda must lie inside configured bounds. | `learning/rl/callbacks.py::LagrangianRiskCallback._on_training_start`; `tests/unit/training/test_lagrangian_callback.py::test_q5_callback_restores_checkpoint_state_and_rejects_config_drift` |
| The environment still owns hard breaches | The environment step checks and records account constraints. Callback shaping cannot weaken its breach latch or create permission to exceed hard floors. | `simulation/environment/episode/constraints.py`; `tests/unit/simulation/test_environment/test_risk_alignment.py` |

## Compatibility and evidence

When behavior or serialized meaning changes, inspect the producer, the
consumer, saved metadata, and the focused test together. The resolved config
and artifact identity are necessary to interpret an actual run. A toy notebook
or source-level test does not establish market quality, policy performance,
or survival qualification.

The source anchors above were read from the pinned baseline. Dirty-source-only
behavior in the active checkout remains unverified. See the
[subject guide](../../subjects/D_learning/constrained-rl.md) and
[Tier A notebook](../../subjects/D_learning/examples/constrained-rl.ipynb).
