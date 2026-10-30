# Experiments Domain Map

## Ownership

Own variant definitions, campaign lifecycle, resource-aware scheduling, resume,
artifact verification, and campaign provenance. Scientific algorithms belong to
their domain packages.

## Boundary

- Campaign lifecycle: `experiments/campaigns/`.
- `campaign_execution.py` is the campaign composition root and composes focused state, source-snapshot, artifact, checkpoint, and compute services.
- `execution.py` is a compatibility adapter for legacy launchers and public imports.
- Cache-failure recovery is owned by `cache_failure_recovery.py`; the old compute resume command forwards to that experiment workflow.
- Variant workflows: `experiments/variants/`.
- May compose training, evaluation, compute, and artifacts at explicit workflow roots.
- Must not import simulation runtime internals or own feature/trading semantics.

## Invariants and Tests

- Preserve campaign identity, source snapshots, checkpoint lineage, and resume state.
- Never create duplicate campaigns or short/fan-out Slurm steps.
- Focused tests: `tests/test_campaign*`, `tests/test_triton_campaign*`.

## Change Map

| Task | Axis | Start file | Contract and test | Expected scope | Keep unchanged |
|---|---|---|---|---|---|
| Change campaign lifecycle | workflow state | `experiments/campaigns/campaign_execution.py` | campaign state/provenance; campaign tests | one lifecycle service and tests | trading and simulation semantics |

## Axis of Change

- **Axis:** campaign lifecycle, resource scheduling, and resume state.
- **Owner:** `experiments/` composes training, evaluation, compute, and artifact services.
- **Stable boundary:** campaign state, source identity, and checkpoint lineage records.
- **Expected edit radius:** one lifecycle service and campaign regression tests.
- **Must not depend on:** simulation runtime internals or feature/trading semantics.

## Verified Source Paths

- `experiments/campaigns/campaign_execution.py`
- `experiments/campaigns/execution.py` (compatibility adapter)
- `experiments/campaigns/cache_failure_recovery.py`
- `experiments/campaigns/state_store.py`
- `compute/slurm/campaign_worker_resources.py`
- `experiments/campaigns/resources.py` (compatibility adapter)
- `experiments/campaigns/source_snapshot.py`
- `experiments/campaigns/artifact_validation.py`
- `experiments/campaigns/checkpoint_lineage.py`
- `experiments/campaigns/constants.py`
- `experiments/variants/variant_ablation_runner.py` (canonical lifecycle; CLI parsing is in `experiments/cli.py`)
- `tests/test_experiments/test_campaign_results_summary.py`
