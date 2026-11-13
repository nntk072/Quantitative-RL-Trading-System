# Run a configured experiment

Use the stable experiment CLI. Research experiments are grouped by scientific
domain and expose independently callable variants through one catalog.

## Research experiments

```bash
uv run qrl-experiment research catalog
uv run qrl-experiment research catalog --domain features
```

Freeze a whole experiment, one component variant, or a named combination of variants:

```bash
uv run qrl-experiment research freeze feature_inputs \
  --variant opportunity_census \
  --output outputs/research/bundles/opportunity_census.json

uv run qrl-experiment research freeze feature_inputs \
  --assembly observation_and_candidate_evidence \
  --output outputs/research/bundles/feature_evidence.json
```

For training experiments, provide the source-bound scientific-readiness record
and pass `--allow-experiments` only when executing the frozen bundle. The
executor never creates or cancels Slurm allocations. Component artifacts
are scoped by experiment and variant to avoid collisions when an implementation
is reused across studies. Completed result artifacts are verified against their
recorded SHA-256 before they contribute metrics.

See [research workflow](../research/workflow.md) for qualification, portfolio,
robustness, result consolidation, and report-only evaluation.

## General experiment runs

```bash
uv run qrl-experiment run --help
uv run qrl-experiment status --help
uv run qrl-experiment summarize --help
```

Recovery must preserve the original run identity and checkpoint lineage.
