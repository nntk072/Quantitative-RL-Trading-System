# Run a configured experiment

An experiment is a declared comparison over resolved variants, data, seed,
training geometry, and evaluation procedure. The experiment runner owns
identity and recovery; it does not redefine market or fill semantics.

## Before launch

1. Read the [experiment-design concept](../concepts/experiment_design.md) and
   [model/variant catalog](../model_variants.md).
2. Resolve each selected variant and compare the effective configuration,
   including its risk policy and feature inputs.
3. Confirm data/cache identity, seed list, step budget, output destination, and
   whether evaluation data have already influenced development.
4. Use a bounded smoke or pilot to validate worker startup and checkpoint
   recovery before a long run.

The current command uses a compatibility-era name:

```bash
uv run qrl-experiment --help
uv run qrl-experiment catalog --check
uv run qrl-experiment run --help
```

Use the configured experiment matrix rather than duplicating settings in a
one-off command. Keep resolved configurations, run fingerprints, manifests,
logs, checkpoints, and evaluation outputs associated with the same run.

## Recovery

Use the runner's status and recovery commands only after inspecting the run
manifest and worker state. Recovery must preserve the existing identity and
record the attempt; do not create a second run to mask an incomplete one. On
Triton, follow the [resource workflow](../operations/triton.md) and the
repository's active agent rules.
