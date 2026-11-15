# Training seeds, resume, and checkpoints

**Status:** Wave D draft
**Use this when:** You need to trace one seed from prepared run to fitted checkpoint and verify exact resume lineage.

## Summary and use this when

A seed labels one stochastic training path inside a resolved run. The training runner prepares that path, loads or constructs its learner, requests remaining steps, and records a content-addressed final checkpoint. Resume depends on the current run contract and checkpoint metadata; finding a ZIP file is only one prerequisite.

- Start with the resolved configuration and the named input/output contracts.
- Follow one transition or fit path in source before interpreting a metric.
- Treat the linked notebook as a mechanics example using bundled synthetic data.

## Key terms

- [Checkpoint](../../glossary.md)
- [Experiment run](../../glossary.md)
- [Lineage](../../glossary.md)
- [Artifact](../../glossary.md)
- [Variant](../../glossary.md)

## Explanation

### Decision or learning boundary

A seed labels one stochastic training path inside a resolved run. The training runner prepares that path, loads or constructs its learner, requests remaining steps, and records a content-addressed final checkpoint. Resume depends on the current run contract and checkpoint metadata; finding a ZIP file is only one prerequisite.

The five source-backed contracts below identify where this subject crosses a
package boundary. Read them together: a policy output has meaning only under
the environment, schema, and run identity that produced it.

### 1. Each seed prepares its own lifecycle

The runner establishes seed-specific output and RNG setup before building environments, callbacks, and model. Multi-seed runs use seeds/seedN directories.

- Source: `training/runner/seed_runtime.py::SeedRunner.prepare_training` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/training/test_seed_reproducibility.py`.
- Practical check: Keep seed identity attached to config and data identity.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 2. Resume requires a local checkpoint and valid schemas

The runner checks the path, loads with prepared environment, validates architecture and observation branches, and rejects a checkpoint with more steps than requested.

- Source: `training/runner/seed_runtime.py::SeedRunner.prepare_training` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Test status: Source-traced runner branch; `tests/unit/learning/test_checkpoint_resume.py` checks the loader as a related component, not this runner branch.
- Practical check: Do not infer compatibility from filename or tensor width.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 3. Remaining steps are explicit

For resumed models, learning_timesteps is requested total minus model.num_timesteps. The stop-candidate schema must match saved metadata.

- Source: `training/runner/seed_runtime.py::SeedRunner.prepare_training` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Test status: Source-traced runner branch; `tests/unit/training/test_periodic_checkpoint.py` checks a related callback, not this step calculation.
- Practical check: Record original and target step counts.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 4. Final checkpoint has a content digest

Fit saves the SB3 model, streams checkpoint bytes through SHA-256, and returns artifact identity and actual completed steps.

- Source: `learning/rl/learner.py::SB3Learner.fit` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/learning/test_learning_contracts.py`.
- Practical check: Use the digest to identify the saved bytes.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

### 5. Experiment resume checks attempt lineage

Automatic candidate selection requires matching attempt provenance and an intact ZIP; explicit parent lineage validation checks fingerprint, run key, seed, step count, and hashes.

- Sources: `experiments/runs/checkpoint_lineage.py::latest_resumable_checkpoint` and `validate_initial_checkpoints` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.
- Focused check: `tests/unit/experiments/test_experiment_run_checkpoint_migration.py`.
- Practical check: Verify provenance and hashes before reusing an interrupted attempt.

This is an implementation contract. It says how the documented path behaves;
it does not by itself qualify a research result or predict a return.

## Worked example

The notebook computes remaining steps and a SHA-256 digest of bundled bytes, then rejects an over-budget checkpoint in a small helper. It creates no file and resumes no training.

Open the [Tier A notebook](examples/training-seeds-resume-checkpoints.ipynb). It runs on CPU using
only deterministic values bundled in the cell. It neither trains nor evaluates
a market policy.

```{toctree}
:hidden:

examples/training-seeds-resume-checkpoints
```

The [compact contract reference](../../reference/subjects/training-seeds-resume-checkpoints.md) records
the exact source-facing obligations for maintainers.

## Tasks

- Record resolved config, data identity, seed, and source revision.
- Check checkpoint metadata against the prepared environment.
- Compare saved and requested step counts before fitting.
- Verify saved bytes and attempt provenance before interpreting a resume result.

## Contract

| Boundary | Required behavior | Source |
|---|---|---|
| Each seed prepares its own lifecycle | The runner establishes seed-specific output and RNG setup before building environments, callbacks, and model. | `training/runner/seed_runtime.py::SeedRunner.prepare_training` |
| Resume requires a local checkpoint and valid schemas | The runner checks the path, loads with prepared environment, validates architecture and observation branches, and rejects a checkpoint with more steps than requested. | `training/runner/seed_runtime.py::SeedRunner.prepare_training` |
| Remaining steps are explicit | For resumed models, learning_timesteps is requested total minus model.num_timesteps. | `training/runner/seed_runtime.py::SeedRunner.prepare_training` |
| Final checkpoint has a content digest | Fit saves the SB3 model, streams checkpoint bytes through SHA-256, and returns artifact identity and actual completed steps. | `learning/rl/learner.py::SB3Learner.fit` |
| Experiment resume checks attempt lineage | Automatic candidate selection checks attempt provenance and ZIP integrity; explicit parent validation checks fingerprint, run key, seed, step count, and hashes. | `experiments/runs/checkpoint_lineage.py::latest_resumable_checkpoint`, `validate_initial_checkpoints` |

## Verify

For this subject, inspect source-traced runner branches and the relevant focused or component tests before changing a contract:

- `tests/unit/training/test_seed_reproducibility.py` — each seed prepares its own lifecycle.
- `training/runner/seed_runtime.py::SeedRunner.prepare_training` — source-traced resume validation and remaining-step arithmetic; no direct focused test of these runner branches. `tests/unit/learning/test_checkpoint_resume.py` checks loading and `tests/unit/training/test_periodic_checkpoint.py` checks a callback as related components.
- `tests/unit/learning/test_learning_contracts.py` — final checkpoint digest and completed steps.
- `tests/unit/experiments/test_experiment_run_checkpoint_migration.py` — experiment resume checks attempt lineage.

The notebook is a deterministic teaching check. A repository test is a
software check. Neither is an out-of-sample result or a claim of economic
performance. Keep those evidence categories separate in reports.

## Limits and common mistakes

- Matching a digest proves byte identity, not scientific validity.
- A seed is not a substitute for multiple independent replicate runs.
- The notebook does not load a checkpoint or execute training.

- Do not use a smoke run as evidence of a strategy effect.
- Do not select a model or threshold using the exposed 2026 reporting interval.
- Preserve invalid, negative, breached, no-trade, and incomplete outcomes.

## Change checklist

Before changing this behavior:

1. Record resolved config, data identity, seed, and source revision.
2. Check checkpoint metadata against the prepared environment.
3. Compare saved and requested step counts before fitting.
4. Verify saved bytes and attempt provenance before interpreting a resume result.
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
