# PPO and rollout geometry

**Status:** Wave D draft
**Use this when:** You need to calculate the rollout collected by the configured PPO builder and reason about minibatch updates.

## Summary and use this when

PPO collects on-policy transitions before updating its actor and value function. This project maps a configured step budget to per-environment steps when vector environments are used. The effective sample count is the product of environment count and per-environment steps; the requested total training timesteps is a different quantity.

- Start with the resolved configuration and the named input/output contracts.
- Follow one transition or fit path in source before interpreting a metric.
- Treat the linked notebook as a mechanics example using bundled synthetic data.

## Key terms

- [PPO](../../glossary.md)
- [GAE](../../glossary.md)
- [Rollout geometry](../../glossary.md)
- [Rollout](../../glossary.md)
- [Episode](../../glossary.md)

## Explanation

### Decision or learning boundary

PPO collects on-policy transitions before updating its actor and value function. This project maps a configured step budget to per-environment steps when vector environments are used. The effective sample count is the product of environment count and per-environment steps; the requested total training timesteps is a different quantity.

The five source-backed contracts below identify where this subject crosses a
package boundary. Read them together: a policy output has meaning only under
the environment, schema, and run identity that produced it.

### 1. Vectorization changes per-env rollout steps

With more than one environment and a provided environment factory, PPO uses max(1, configured n_steps // n_envs). Otherwise it keeps configured n_steps.

- Source: `learning/rl/agent.py::build_agent` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: No direct test of this builder arithmetic; source-traced contract.
- Practical check: Calculate effective samples after the same branch used by the builder.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 2. PPO receives configured optimization settings

The builder passes batch_size, n_epochs, learning_rate, gamma, gae_lambda, and clip_range from cfg.ppo to SB3 PPO. `_ppo_policy_and_ent_coef` retains `ent_coef` for discrete actions and selects `ent_coef_continuous` for Box actions.

- Sources: `learning/rl/agent.py::build_agent` and `_ppo_policy_and_ent_coef` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/models/test_ppo_log_std.py`.
- Practical check: Read the resolved config before interpreting a training log.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 3. Actor head depends on the action schema

`build_agent` selects semantic actor heads from `ppo.actor_arch` and rejects them unless the action space is continuous Box with a declared strategy `ActionSchema`. `_ppo_policy_and_ent_coef` then selects the matching policy class and entropy coefficient.

- Sources: `learning/rl/agent.py::build_agent` and `_ppo_policy_and_ent_coef` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Test status: The semantic-head Box/schema guard is source-traced. `tests/unit/models/test_semantic_actor.py` checks the selected policy as a related component.
- Practical check: Validate action meaning, not only the number of coordinates.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 4. Optional rollout storage changes placement

Collection stays in NumPy arrays; a full rollout is staged on the learner device for minibatch indexing. The optional switch changes storage mechanics, not the conceptual sample count.

- Source: `learning/rl/rollout_buffer.py::DeviceDictRolloutBuffer` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/models/test_rollout_copy.py`.
- Practical check: Keep device allocation separate from rollout geometry.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 5. The learning port records completed steps

The fit call requests remaining steps, then saves a checkpoint and records actual model.num_timesteps plus its SHA-256 artifact identity.

- Source: `learning/rl/learner.py::SB3Learner.fit` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/learning/test_learning_contracts.py`.
- Practical check: Use recorded training_steps for provenance, not requested_steps alone.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

## Worked example

The notebook calculates effective samples for a small configured budget and compares full and partial minibatches. It does not instantiate SB3 or train a policy.

Open the [Tier A notebook](examples/ppo-and-rollout-geometry.ipynb). It runs on CPU using
only deterministic values bundled in the cell. It neither trains nor evaluates
a market policy.

```{toctree}
:hidden:

examples/ppo-and-rollout-geometry
```

The [compact contract reference](../../reference/subjects/ppo-and-rollout-geometry.md) records
the exact source-facing obligations for maintainers.

## Tasks

- Read n_envs, n_steps, and batch_size from the resolved run config.
- Calculate effective samples using the builder branch.
- Check whether the final minibatch is partial.
- Compare requested and actual completed timesteps in a fit result.

## Contract

| Boundary | Required behavior | Source |
|---|---|---|
| Vectorization changes per-env rollout steps | With more than one environment and a provided environment factory, PPO uses max(1, configured n_steps // n_envs). | `learning/rl/agent.py::build_agent` |
| PPO receives configured optimization settings | The builder passes batch_size, n_epochs, learning_rate, gamma, gae_lambda, and clip_range from cfg.ppo; `_ppo_policy_and_ent_coef` keeps `ent_coef` for discrete actions and uses `ent_coef_continuous` for Box actions. | `learning/rl/agent.py::build_agent`, `_ppo_policy_and_ent_coef` |
| Actor head depends on the action schema | `build_agent` requires Box and a declared strategy `ActionSchema` for semantic heads; `_ppo_policy_and_ent_coef` selects the policy class. | `learning/rl/agent.py::build_agent`, `_ppo_policy_and_ent_coef` |
| Optional rollout storage changes placement | Collection stays in NumPy arrays; a full rollout is staged on the learner device for minibatch indexing. | `learning/rl/rollout_buffer.py::DeviceDictRolloutBuffer` |
| The learning port records completed steps | The fit call requests remaining steps, then saves a checkpoint and records actual model.num_timesteps plus its SHA-256 artifact identity. | `learning/rl/learner.py::SB3Learner.fit` |

## Verify

For this subject, inspect source-traced builder branches and the relevant focused or component tests before changing a contract:

- PPO rollout arithmetic is source-traced at `learning/rl/agent.py::build_agent`; no direct focused test asserts the formula.
- `tests/unit/models/test_ppo_log_std.py` — ppo receives configured optimization settings.
- Semantic-head Box/schema validation is source-traced at `learning/rl/agent.py::build_agent`; `tests/unit/models/test_semantic_actor.py` checks the policy as a related component.
- `tests/unit/models/test_rollout_copy.py` — optional rollout storage changes placement.
- `tests/unit/learning/test_learning_contracts.py` — the learning port records completed steps and checkpoint digest.

The notebook is a deterministic teaching check. A repository test is a
software check. Neither is an out-of-sample result or a claim of economic
performance. Keep those evidence categories separate in reports.

## Limits and common mistakes

- The toy calculation does not model SB3 update scheduling or convergence.
- A larger rollout does not imply a better policy.
- Training or economic performance requires run artifacts and a frozen protocol.

- Do not use a smoke run as evidence of a strategy effect.
- Do not select a model or threshold using the exposed 2026 reporting interval.
- Preserve invalid, negative, breached, no-trade, and incomplete outcomes.

## Change checklist

Before changing this behavior:

1. Read n_envs, n_steps, and batch_size from the resolved run config.
2. Calculate effective samples using the builder branch.
3. Check whether the final minibatch is partial.
4. Compare requested and actual completed timesteps in a fit result.
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
