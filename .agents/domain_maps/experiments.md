# Experiments Domain Map

## Ownership

Own variant definitions, experiment run lifecycle, resource-aware scheduling, resume,
artifact verification, and experiment run provenance. Scientific algorithms belong to
their domain packages.

## Allocation-aware worker pool

Pass `--workers auto --worker-cpus auto` for a pooled run. The controller plans
slots per node from the Slurm CPU set, cgroup RAM limit, and visible GPU memory,
then divides CPUs among those slots and leaves one CPU for the resource sampler.
For the 8-environment bundle profile the conservative RAM estimate is 19 GiB per
worker, with a 35% margin and 64 GiB per-node reserve; GH200 sharing is capped at
9 workers per allocated GPU using an 8 GiB per-worker VRAM estimate and 20% GPU
reserve. The controller queues the full variant list and keeps the resource-sized
pool busy as workers finish. If a resource limit cannot be read, it admits only
one worker per node rather than assuming unlimited capacity. Explicit worker
counts remain supported for controlled comparisons. For 8-environment bundle
workers, nine per GH200 need about 295 GiB per node under this estimate; request
at least 512 GiB per node when that concurrency is desired. Smaller allocations
automatically use fewer slots.

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
