# Orchestra

Orchestra coordinates multi-stage engineering tasks such as triage, planning,
implementation, review, and verification. It is a development workflow tool,
not part of the trading policy or training environment.

The pipeline stores task state and phase outputs so a task can be reviewed and
resumed. Each phase has a distinct contract; verification is responsible for
running the configured repository gate and reporting exact results. Provider
selection, model routing, and orchestration costs are operational concerns,
not evidence about trading performance.

Run `orchestra doctor` for a no-inference health check and consult
`.agents/rules/` for repository-specific agent behavior. The package-local
implementation overview complements the [Orchestra module guide](../docs/modules/orchestra.md).

## Pipeline contract

The CLI accepts a task and routes it through configured phases. Each phase
receives a bounded input contract and stores its output/state so the workflow
can be inspected and resumed. The verification phase is responsible for
running the exact configured gate; a successful planning or implementation
phase is not a passing verification result.

Keep provider-specific inference behind the provider interfaces and persistent
task data behind the orchestra state/artifact boundary. Do not put trading
metrics or research conclusions into orchestration status without a linked
experiment artifact. Focused tests are under `tests/unit/orchestra/`; the
configured phase-nine check exercises the integrated gate.

## Delegation and measurement

By default, triage complexity selects the smallest team: trivial/T0 tasks use
no planners, critics, or reviewers; routine T1/T2 tasks use one planner and
one reviewer; complex/T3/T4 tasks use two planners, one critic, and two
reviewers. Triage route values and `--planners`, `--critics`, and `--reviewers`
override these defaults; zero is an explicit valid value. The model router
continues to use its existing availability and capability fallback.

New run telemetry records estimated prompt/output tokens, configured or
fallback-estimate cost, measured CLI wall time, retries, phase concurrency,
call success, and pipeline status. Cached-token and internal tool-call counts
remain `unknown` when the provider CLI does not expose them. `orchestra
cost-task <task-id>` reports the available fields. To compare orchestration
modes, run the same frozen task inputs and source/environment in isolated state
directories, label each task with its mode, and compare task-level token,
cost, elapsed-time, retry, validation, and completion records. Use provider
usage when available; the existing character-based token estimate and fallback
price are not billable usage. Do not claim an end-to-end improvement from
delegation-count arithmetic or synthetic tests alone.
