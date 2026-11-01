# Experiment run reference

An experiment run is a reproducible controller for a declared set of
variant/seed jobs. It connects resolved configuration, data and source
identity, worker attempts, checkpoints, evaluations, and a generated summary.
It is distinct from an individual training run, one evaluation, a comparison,
or a research finding.

## Identity and lifecycle

The run ID selects a stable artifact directory. Each worker job has a key
derived from variant and seed and records its status and attempt count. The
controller lifecycle is:

```text
validate request → resolve configuration → record run identity and provenance
→ schedule worker attempt → validate outputs/checkpoint lineage
→ evaluate compatible checkpoint → summarize statuses and evidence
```

The controller records pending, running, succeeded, failed, and interrupted
states. Interrupted or failed attempts remain represented in the run ledger;
resume logic validates inputs, source fingerprints, checkpoint identity, and
attempt paths before continuing. A successful worker status alone does not
establish that its evidence passed research gates.

## Core files

| Artifact | Role |
|---|---|
| `experiment_run.json` | Resolved run specification, identity, and execution inputs. |
| `experiment_run_status.json` | Controller timestamp, status counts, and per-job attempt state. |
| `queue.jsonl` | Append-only job events such as start, completion, interruption, and failure. |
| `runs/attempts/<run-key>/attempt<n>/` | Isolated worker-attempt outputs, logs, checkpoints, and training/evaluation records. |
| `reports/experiment_run_results_summary.json` and `.md` | Derived status, artifact verification, metrics, and reconciliation report. |

Exact locations are resolved by `artifacts/layout.py` and the
`ExperimentRunArtifactLayout`; use that layout rather than reconstructing paths
in consumers. Artifact writers record action/observation schemas, feature
columns, resolved configuration, seed, requested/effective training settings,
source revision, and hashes where applicable.

## Identity and validation

`experiments/runs/source_snapshot.py` records the source revision and selected
source-file hashes. Artifact validation checks that run keys, variants, seeds,
attempts, checkpoint provenance, and run outputs agree. Comparisons should
consume verified reports from matched protocols; a folder name or status table
is not a causal result.

Use `qrl-experiment` for supported experiment operations. Read the
[experiment runtime sequence](../architecture/runtime/experiment_run.md),
[CLI reference](cli.md), [artifact reference](artifacts.md), and
[research validation protocol](../research/validation_protocol.md) before
interpreting a campaign summary.
