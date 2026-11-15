# Training seeds, resume, and checkpoints contract

This page records the subject-specific contract at source revision
`c0d982f94ab9df8b2a9ddd013d2ae9a562573529`. The generated API pages describe callable signatures;
the entries below record cross-package meaning and validation obligations.

## Contract table

| Contract | Exact obligation | Source and test status |
|---|---|---|
| Each seed prepares its own lifecycle | The runner establishes seed-specific output and RNG setup before building environments, callbacks, and model. Multi-seed runs use seeds/seedN directories. | `training/runner/seed_runtime.py::SeedRunner.prepare_training`; `tests/unit/training/test_seed_reproducibility.py` |
| Resume requires a local checkpoint and valid schemas | The runner checks the path, loads with prepared environment, validates architecture and observation branches, and rejects a checkpoint with more steps than requested. | `training/runner/seed_runtime.py::SeedRunner.prepare_training` (source-traced; no direct runner test). `tests/unit/learning/test_checkpoint_resume.py` checks the loader as a related component. |
| Remaining steps are explicit | For resumed models, learning_timesteps is requested total minus model.num_timesteps. The stop-candidate schema must match saved metadata. | `training/runner/seed_runtime.py::SeedRunner.prepare_training` (source-traced; no direct runner test). `tests/unit/training/test_periodic_checkpoint.py` checks a related callback. |
| Final checkpoint has a content digest | Fit saves the SB3 model, streams checkpoint bytes through SHA-256, and returns artifact identity and actual completed steps. | `learning/rl/learner.py::SB3Learner.fit`; `tests/unit/learning/test_learning_contracts.py` |
| Experiment resume checks attempt lineage | Automatic candidate selection checks attempt provenance and ZIP integrity; explicit parent validation checks fingerprint, run key, seed, step count, and hashes. | `experiments/runs/checkpoint_lineage.py::latest_resumable_checkpoint`, `validate_initial_checkpoints`; `tests/unit/experiments/test_experiment_run_checkpoint_migration.py` |

## Compatibility and evidence

When behavior or serialized meaning changes, inspect the producer, the
consumer, saved metadata, and the focused test together. The resolved config
and artifact identity are necessary to interpret an actual run. A toy notebook
or source-level test does not establish market quality, policy performance,
or survival qualification.

The source anchors above were read from the pinned baseline. Dirty-source-only
behavior in the active checkout remains unverified. See the
[subject guide](../../subjects/D_learning/training-seeds-resume-checkpoints.md) and
[Tier A notebook](../../subjects/D_learning/examples/training-seeds-resume-checkpoints.ipynb).
