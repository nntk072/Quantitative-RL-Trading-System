# Experiments

`experiments/` resolves variant definitions and coordinates comparable runs,
provenance, recovery, and evaluation handoff. A variant describes a configured
model/run choice; an experiment comparison defines which factors differ and
which outcomes answer the research question.

| Area | Responsibility |
|---|---|
| `variants/` | Resolve selectable configurations and model/encoder identities. |
| `campaigns/` | Coordinate run lifecycle and status. |
| `runs/`, `provenance/` | Record run identities and input/source evidence. |
| `orchestration/` | Manage multi-run workflow. |
| `cli.py` | Experiment command surface. |

Actual settings belong in configuration, not catalog prose. Do not edit a
frozen run record to make it match current defaults. Comparisons must preserve
their declared matched factors, split, seed, and execution assumptions.

See the [experiment guide](../docs/modules/experiments.md),
[generated catalog](../docs/model_variants.md), and
[research validation protocol](../docs/thesis/validation_protocol.md).

## Run lifecycle

```mermaid
flowchart LR
    Matrix[Experiment matrix] --> Resolver[Variant resolution]
    Resolver --> Identity[Run identity and manifest]
    Identity --> Worker[Training attempt]
    Worker --> Checkpoint[Checkpoint and diagnostics]
    Checkpoint --> Evaluate[Evaluation handoff]
    Evaluate --> Summary[Comparison result]
```

Variant resolution turns named settings into an effective configuration.
Orchestration assigns run identities and coordinates attempts; recovery checks
that identity before resuming. Summaries should retain the arm, seed, data
period, checkpoint, and evaluation protocol so a reader can distinguish
matched comparisons from a loose collection of runs.

Catalog labels explain research roles only. They do not override runtime YAML.
Keep historical run records immutable and create a new run identity when an
experimental factor changes. Focused tests are under
`tests/unit/experiments/`; worker lifecycle tests also live with training and
orchestration.
