# Soft Actor-Critic (SAC) contract

This page records the subject-specific contract at source revision
`c0d982f94ab9df8b2a9ddd013d2ae9a562573529`. The generated API pages describe callable signatures;
the entries below record cross-package meaning and validation obligations.

## Contract table

| Contract | Exact obligation | Source and focused test |
|---|---|---|
| SAC requires continuous actions | The SAC branch rejects an action space that is not Gymnasium Box before constructing the model. Categorical actions must use another supported policy path. | `learning/rl/agent.py::build_agent`; `tests/unit/models/test_sac_agent.py` |
| SAC uses a Q-function head | The builder sets `net_arch=dict(pi=head_arch, qf=head_arch)` for SAC, versus `vf` for PPO, and constructs SAC `MultiInputPolicy` with configured feature extractor options. | `learning/rl/agent.py::build_agent`; `tests/unit/models/test_sac_agent.py` |
| Replay and update settings come from config | The builder passes buffer_size, batch_size, tau, gamma, train_freq, gradient_steps, ent_coef, and learning_starts from the SAC configuration. | `learning/rl/agent.py::build_agent`; `tests/unit/training/test_sac_smoke.py` |
| Action schema persists with the model | The builder attaches declared Box action semantics to the SB3 model and policy. Strategy actions without a declarative schema fail. | `learning/rl/agent.py::persist_action_schema`; `tests/unit/models/test_action_schema_checkpoint.py` |
| Training checkpoint loading selects the algorithm | The loader accepts only ppo or sac and binds the caller-prepared environment on resume. It does not infer the algorithm from the file name. | `learning/rl/checkpoint.py::load_sb3_training_checkpoint`; `tests/unit/learning/test_checkpoint_resume.py` |

## Compatibility and evidence

When behavior or serialized meaning changes, inspect the producer, the
consumer, saved metadata, and the focused test together. The resolved config
and artifact identity are necessary to interpret an actual run. A toy notebook
or source-level test does not establish market quality, policy performance,
or survival qualification.

The source anchors above were read from the pinned baseline. Dirty-source-only
behavior in the active checkout remains unverified. See the
[subject guide](../../subjects/D_learning/sac.md) and
[Tier A notebook](../../subjects/D_learning/examples/sac.ipynb).
