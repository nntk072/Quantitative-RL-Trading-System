# Experiment framework

`experiments/` connects reusable model configurations, scientific questions,
execution, recovery, and provenance. It does not replace the implementations
owned by data, features, simulation, training, or evaluation.

| Module | Contract |
|---|---|
| `research/catalog.py` | Validate component implementations, experiment variants, and named assemblies |
| `research/workflow.py` | Freeze selected variants into source-bound execution bundles |
| `research/execution.py` | Execute dependency-safe commands, resume compatible attempts, and hash outputs |
| `research/reporting.py` | Normalize execution results into JSON, wide CSV, and long-form metrics |
| `variants/` | Resolve model and configuration factors for training |
| `runs/` | Durable training-run attempts, recovery, and checkpoint lineage |
| `orchestration/` | Coordinate multi-run workflows |
| `cli.py` | Public `qrl-experiment` command surface |

## Defining a study

`config/research/experiments.yaml` is the single source for research
component implementations and their uses. A component implementation may be
referenced by multiple experiments. Within an experiment, variants select
implementations and express local changes; an assembly selects compatible
variants for one comparison or analysis.

Adding an experiment does not require copying an implementation, adding another
execution entry point, or building a new report parser. Runtime records retain
the source revision, seed, component, variant, command, artifact, and digest.

```bash
uv run qrl-experiment research catalog
uv run qrl-experiment research catalog --component observations
uv run qrl-experiment research freeze feature_inputs \
  --assembly observation_and_candidate_evidence \
  --output outputs/research/bundles/features.json
```

See [research workflow](../docs/research/workflow.md) for execution, resume,
comparison, and consolidation. Existing training-run recovery and research
source-bound command execution have different responsibilities; both preserve
the same scientific identities without rewriting historical evidence.
