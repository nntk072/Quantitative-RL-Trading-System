# Research workflow

Research is organized by **domain → experiment → component → variant**. The executable
catalog is [`config/research/experiments.yaml`](../../config/research/experiments.yaml);
documentation explains the contract but does not duplicate its settings.

## Domains

| Domain | Scope |
|---|---|
| Validation | Prospective protocol, source identity, software contracts, reproducibility |
| Data | Market inputs, dataset identity, denominators, quote coverage |
| Features | Causal feature construction, availability, missingness, candidate support |
| Policy | Observation/action representation, ablations, survival qualification |
| Portfolio | Qualified-checkpoint continuation and matched economic comparison |
| Execution | Fill, quote, latency, slippage, simulator/broker sensitivity |
| Robustness | Account-rule, risk, regime, and policy sensitivity |
| Reporting | Consolidated results, report-only evaluation, research study/release evidence |

An experiment owns one scientific question, not a separate copy of the pipeline.
The catalog declares reusable component implementations under `components`;
experiment variants reference them with `use`. A named `assembly` selects a
compatible set of variants, at most one per component, without introducing a
new experiment ID or runner. Component implementations can be reused by
different experiments, while experiment-local overrides remain explicit.
Artifact destinations for shared component templates use `{experiment_id}` and
`{variant_id}` placeholders; reused components cannot write into another
experiment's result directory.

The execution engine is shared regardless of which component provides a command.
Add new experimental treatments as catalog data when an existing implementation
supports them. Add Python only for genuinely different behavior, then register
that implementation once.

## Inspect and freeze

```bash
uv run qrl-experiment research catalog
uv run qrl-experiment research catalog --domain policy
uv run qrl-experiment research catalog --component observations

# Freeze a named combination of component variants.
uv run qrl-experiment research freeze feature_inputs \
  --assembly observation_and_candidate_evidence \
  --output outputs/research/bundles/feature_evidence.json

# Run one independent component from a multi-component experiment.
uv run qrl-experiment research freeze feature_inputs \
  --component observations \
  --output outputs/research/bundles/feature_observations.json

uv run qrl-experiment research freeze candidate_history \
  --variant shared_opportunities \
  --readiness outputs/research/readiness.json \
  --output outputs/research/bundles/candidate_history.json
```

Omit `--variant` to freeze every registered variant in the experiment. Frozen
bundles bind commands to the current source commit and may be executed only
from the same clean checkout.

## Execute and resume

```bash
uv run qrl-experiment research execute \
  --bundle outputs/research/bundles/candidate_history.json \
  --run-root outputs/research/executions/candidate_history \
  --max-workers 8 \
  --allow-experiments
```

The executor does not create or cancel Slurm allocations. Resource locks
serialize GPU training while independent CPU/data work may run concurrently.
Interrupted work can be resumed. A reviewed failed command may be retried with
`--resume --retry-failed`; completed artifacts are hash-checked before reuse.

## Result consolidation

Execution-specific directories are not the research index. Consolidate one or
more execution manifests into a domain-oriented JSON/CSV catalog:

```bash
uv run qrl-experiment research consolidate \
  --execution outputs/research/executions/data_integrity/execution_manifest.json \
  --execution outputs/research/executions/candidate_history/execution_manifest.json \
  --output outputs/research/results
```

The result catalog keeps the domain, experiment, component, variant, command,
explicit seed, source commit, execution status, selected result artifact, content
digest, and scalar metrics together. The consolidator checks file bytes against
the recorded SHA-256 and rejects altered or missing declared outputs instead
of silently publishing stale metrics. `results.json` preserves complete records;
`results.csv` provides wide rows; `metrics.csv` provides tidy long-form data
with one observation per metric and execution identity. It deduplicates identical manifest entries and rejects conflicting
records for the same command and artifact identity. Both machine-readable
outputs use the same columns, regardless of which component produced a result.

The component label is part of the execution record, not reconstructed from
file names. Older manifests remain readable, with missing component identity
attributed to their recorded domain rather than guessed.

## Historical evidence

Historical research uses the same domain taxonomy:

```bash
uv run qrl-experiment research history
```

The source catalog is [`config/research/history.yaml`](../../config/research/history.yaml).
It rewrites the **index and interpretation**, not the bytes of historical
evidence. Original artifacts and checksums remain under `evidence/research/`.

## Scientific ordering

The prospective protocol remains authoritative:

1. source/data/feature/execution prerequisites;
2. candidate-history secondary ablation;
3. registered primary survival policy qualification;
4. qualified-checkpoint portfolio continuation;
5. matched always-no-trade primary comparison;
6. development-only robustness;
7. one-time exposed-period report after the finalist is frozen.

A negative result is a valid final research outcome. The workflow must not
invent replacement candidates or alter thresholds after observing outcomes.
