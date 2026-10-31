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
