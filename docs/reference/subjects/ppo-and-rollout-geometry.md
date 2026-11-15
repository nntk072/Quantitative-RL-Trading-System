# PPO and rollout geometry contract

This page records the subject-specific contract at source revision
`c0d982f94ab9df8b2a9ddd013d2ae9a562573529`. The generated API pages describe callable signatures;
the entries below record cross-package meaning and validation obligations.

## Contract table

| Contract | Exact obligation | Source and test status |
|---|---|---|
| Vectorization changes per-env rollout steps | With more than one environment and a provided environment factory, PPO uses max(1, configured n_steps // n_envs). Otherwise it keeps configured n_steps. No direct focused test asserts this builder arithmetic. | `learning/rl/agent.py::build_agent` (source-traced) |
| PPO receives configured optimization settings | The builder passes batch_size, n_epochs, learning_rate, gamma, gae_lambda, and clip_range from cfg.ppo; `_ppo_policy_and_ent_coef` keeps `ent_coef` for discrete actions and uses `ent_coef_continuous` for Box actions. | `learning/rl/agent.py::build_agent`, `_ppo_policy_and_ent_coef`; `tests/unit/models/test_ppo_log_std.py` |
| Actor head depends on the action schema | `build_agent` selects semantic heads from `ppo.actor_arch` and requires Box plus a declared strategy `ActionSchema`; `_ppo_policy_and_ent_coef` selects the policy class. | `learning/rl/agent.py::build_agent`, `_ppo_policy_and_ent_coef` (source-traced guard); `tests/unit/models/test_semantic_actor.py` checks the policy as a related component. |
| Optional rollout storage changes placement | Collection stays in NumPy arrays; a full rollout is staged on the learner device for minibatch indexing. The optional switch changes storage mechanics, not the conceptual sample count. | `learning/rl/rollout_buffer.py::DeviceDictRolloutBuffer`; `tests/unit/models/test_rollout_copy.py` |
| The learning port records completed steps | The fit call requests remaining steps, then saves a checkpoint and records actual model.num_timesteps plus its SHA-256 artifact identity. | `learning/rl/learner.py::SB3Learner.fit`; `tests/unit/learning/test_learning_contracts.py` |

## Compatibility and evidence

When behavior or serialized meaning changes, inspect the producer, the
consumer, saved metadata, and the focused test together. The resolved config
and artifact identity are necessary to interpret an actual run. A toy notebook
or source-level test does not establish market quality, policy performance,
or survival qualification.

The source anchors above were read from the pinned baseline. Dirty-source-only
behavior in the active checkout remains unverified. See the
[subject guide](../../subjects/D_learning/ppo-and-rollout-geometry.md) and
[Tier A notebook](../../subjects/D_learning/examples/ppo-and-rollout-geometry.ipynb).
