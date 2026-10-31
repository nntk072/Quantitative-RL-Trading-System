# Run a training job

This workflow is for a reproducible training run, not a throughput probe or
approval to launch a long experiment.

1. Select a configured variant and inspect its resolved settings. Do not infer
   defaults from another variant.
2. Verify the chronological data split and identify whether the evaluation
   interval has already influenced development.
3. Prepare and validate reusable data/features before allocating long-running
   training resources. Record cache identity and source data identity.
4. Confirm the selected algorithm, encoder, observation schema, action schema,
   reward, account limits, costs, and seed.
5. Run the smallest documented smoke first, then a bounded pilot when needed.
   Label outputs as smoke/pilot; do not present them as full results.
6. Run the declared training budget and retain checkpoint, resolved config,
   logs, and run manifest together.
7. Evaluate a frozen checkpoint with matching schema and execution settings.
   Produce trade/equity ledgers before summarizing metrics.

On Triton, follow [resource operations](../operations/triton.md) and
`.agents/rules/triton-slurm.md`. Preserve active allocations and run identity;
do not duplicate a run to recover a worker failure.

Current command names can be inspected without starting a job:

```bash
uv run qrl-train train --help
uv run qrl-experiment --help
```

The `thesis-*` names are deprecated compatibility aliases. New run
instructions should use the canonical `qrl-*` commands.
