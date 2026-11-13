# Experiment orchestration

`experiments/orchestration/` groups declared experiment runs into weekly and
batch reports. Its `BatchSpec` and `RunSpec` records carry the requested run
inputs; `WeeklyOrchestrator` invokes a runner, records attempt results, and
renders summaries for the batch and week.

This layer coordinates runs but does not define variant semantics or infer
comparability from labels. Run identity and resolved configuration determine
whether results can be combined. Keep failures and retries visible in the
written report.

Focused tests are in `tests/unit/experiments/`. See the
[experiment run guide](../../experiments/runs/README.md) and
[research execution plan](../../docs/research/workflow.md).
