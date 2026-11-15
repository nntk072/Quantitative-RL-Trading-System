# Soft Actor-Critic (SAC)

**Status:** Wave D draft
**Use this when:** You need to distinguish this off-policy continuous-control path from PPO and check its action-space and replay settings.

## Summary and use this when

SAC is the configured off-policy alternative to PPO. Its replay buffer and entropy coefficient belong to the SB3 SAC implementation; the repository builder supplies their settings and a named observation policy. The environment action schema still determines what continuous output coordinates mean.

- Start with the resolved configuration and the named input/output contracts.
- Follow one transition or fit path in source before interpreting a metric.
- Treat the linked notebook as a mechanics example using bundled synthetic data.

## Key terms

- [SAC](../../glossary.md)
- [Action schema](../../glossary.md)
- [Rollout](../../glossary.md)
- [Checkpoint](../../glossary.md)
- [Episode](../../glossary.md)

## Explanation

### Decision or learning boundary

SAC is the configured off-policy alternative to PPO. Its replay buffer and entropy coefficient belong to the SB3 SAC implementation; the repository builder supplies their settings and a named observation policy. The environment action schema still determines what continuous output coordinates mean.

The five source-backed contracts below identify where this subject crosses a
package boundary. Read them together: a policy output has meaning only under
the environment, schema, and run identity that produced it.

### 1. SAC requires continuous actions

The SAC branch rejects an action space that is not Gymnasium Box before constructing the model. Categorical actions must use another supported policy path.

- Source: `learning/rl/agent.py::build_agent` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/models/test_sac_agent.py`.
- Practical check: Check action space type before setting algo=sac.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 2. SAC uses a Q-function head

The builder sets `net_arch=dict(pi=head_arch, qf=head_arch)` for SAC, while PPO uses `vf` in place of `qf`. SAC uses `MultiInputPolicy` with the configured feature extractor class and options.

- Source: `learning/rl/agent.py::build_agent` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/models/test_sac_agent.py`.
- Practical check: Do not read a PPO value-function head as a SAC Q-function.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 3. Replay and update settings come from config

The builder passes buffer_size, batch_size, tau, gamma, train_freq, gradient_steps, ent_coef, and learning_starts from the SAC configuration.

- Source: `learning/rl/agent.py::build_agent` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/training/test_sac_smoke.py`.
- Practical check: Record resolved settings with each run.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 4. Action schema persists with the model

The builder attaches declared Box action semantics to the SB3 model and policy. Strategy actions without a declarative schema fail.

- Source: `learning/rl/agent.py::persist_action_schema` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/models/test_action_schema_checkpoint.py`.
- Practical check: A Box width cannot recover action meanings.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 5. Training checkpoint loading selects the algorithm

The loader accepts only ppo or sac and binds the caller-prepared environment on resume. It does not infer the algorithm from the file name.

- Source: `learning/rl/checkpoint.py::load_sb3_training_checkpoint` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/learning/test_checkpoint_resume.py`.
- Practical check: Use the source run algorithm and prepared environment.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

## Worked example

The notebook keeps a three-transition replay list and computes a fixed weighted reward example. It illustrates reuse of stored samples only; it is not an SAC implementation.

Open the [Tier A notebook](examples/sac.ipynb). It runs on CPU using
only deterministic values bundled in the cell. It neither trains nor evaluates
a market policy.

```{toctree}
:hidden:

examples/sac
```

The [compact contract reference](../../reference/subjects/sac.md) records
the exact source-facing obligations for maintainers.

## Tasks

- Confirm the environment exposes a Box action space.
- Read the resolved sac block and its replay/update settings.
- Compare policy action schema metadata before replay or inference.
- Keep algorithm choice alongside the checkpoint lineage.

## Contract

| Boundary | Required behavior | Source |
|---|---|---|
| SAC requires continuous actions | The SAC branch rejects an action space that is not Gymnasium Box before constructing the model. | `learning/rl/agent.py::build_agent` |
| SAC uses a Q-function head | The builder sets `net_arch` with `pi` and `qf` for SAC, versus `pi` and `vf` for PPO, and configures the SAC feature extractor. | `learning/rl/agent.py::build_agent` |
| Replay and update settings come from config | The builder passes buffer_size, batch_size, tau, gamma, train_freq, gradient_steps, ent_coef, and learning_starts from the SAC configuration. | `learning/rl/agent.py::build_agent` |
| Action schema persists with the model | The builder attaches declared Box action semantics to the SB3 model and policy. | `learning/rl/agent.py::persist_action_schema` |
| Training checkpoint loading selects the algorithm | The loader accepts only ppo or sac and binds the caller-prepared environment on resume. | `learning/rl/checkpoint.py::load_sb3_training_checkpoint` |

## Verify

For this subject, inspect the focused tests before changing a contract:

- `tests/unit/models/test_sac_agent.py` — sac requires continuous actions.
- `tests/unit/models/test_sac_agent.py` — sac uses a q-function head.
- `tests/unit/training/test_sac_smoke.py` — replay and update settings come from config.
- `tests/unit/models/test_action_schema_checkpoint.py` — action schema persists with the model.
- `tests/unit/learning/test_checkpoint_resume.py` — training checkpoint loading selects the algorithm.

The notebook is a deterministic teaching check. A repository test is a
software check. Neither is an out-of-sample result or a claim of economic
performance. Keep those evidence categories separate in reports.

## Limits and common mistakes

- A toy replay list cannot test entropy optimization or Bellman backups.
- SAC support does not establish suitability for every strategy action mode.
- No return or sample-efficiency claim follows from this page.

- Do not use a smoke run as evidence of a strategy effect.
- Do not select a model or threshold using the exposed 2026 reporting interval.
- Preserve invalid, negative, breached, no-trade, and incomplete outcomes.

## Change checklist

Before changing this behavior:

1. Confirm the environment exposes a Box action space.
2. Read the resolved sac block and its replay/update settings.
3. Compare policy action schema metadata before replay or inference.
4. Keep algorithm choice alongside the checkpoint lineage.
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
