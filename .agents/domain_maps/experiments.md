# Experiments Domain Map

## Ownership

Own variant definitions, experiment run lifecycle, resource-aware scheduling, resume,
artifact verification, and experiment run provenance. Scientific algorithms belong to
their domain packages.

## Boundary

- Experiment run lifecycle: `experiments/runs/`.
- `execution.py` is the canonical experiment run composition root; it composes
  focused state, source-snapshot, artifact, checkpoint, and compute services.
- Cache-failure recovery is owned by `cache_failure_recovery.py` and exposed through `thesis-experiment-run recover-cache`.
- Variant workflows: `experiments/variants/`.
- May compose training, evaluation, compute, and artifacts at explicit workflow roots.
- Must not import simulation runtime internals or own feature/trading semantics.

## Invariants and Tests

- Preserve experiment run identity, source snapshots, checkpoint lineage, and resume state.
- Never create duplicate experiment runs or short/fan-out Slurm steps.
- Focused tests: `tests/unit/experiments/` and `tests/unit/compute/`.

## Change Map

| Task | Axis | Start file | Contract and test | Expected scope | Keep unchanged |
|---|---|---|---|---|---|
| Change experiment run lifecycle | workflow state | `experiments/runs/execution.py` | experiment run state/provenance; experiment run tests | one lifecycle service and tests | trading and simulation semantics |

## Axis of Change

- **Axis:** experiment run lifecycle, resource scheduling, and resume state.
- **Owner:** `experiments/` composes training, evaluation, compute, and artifact services.
- **Stable boundary:** experiment run state, source identity, and checkpoint lineage records.
- **Expected edit radius:** one lifecycle service and experiment run regression tests.
- **Must not depend on:** simulation runtime internals or feature/trading semantics.

## Verified Source Paths

- `experiments/runs/execution.py`
- `experiments/runs/cache_failure_recovery.py`
- `experiments/runs/state_store.py`
- `compute/slurm/worker_resources.py`
- `experiments/runs/source_snapshot.py`
- `experiments/runs/artifact_validation.py`
- `experiments/runs/checkpoint_lineage.py`
- `experiments/runs/constants.py`
- `experiments/variants/variant_ablation_runner.py` (canonical lifecycle; CLI parsing is in `experiments/cli.py`)
- `tests/unit/experiments/test_experiment_run_results_summary.py`
