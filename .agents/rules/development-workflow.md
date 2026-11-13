---
trigger: model_decision
description: "Use before implementing a non-trivial feature or bug fix."
---

# Development workflow

The full feature development process that happens before git operations: research, planning, TDD, code review, then committing.

## Feature implementation pipeline

**Research and reuse first**
   - Search the owning production package and its current callers before adding behavior.
   - Consult external libraries when the implementation genuinely needs a new dependency; external network access is not a prerequisite for routine refactoring.
   - Prefer existing validated components under `features/`, `simulation/`, and `trading/` to copies in experiment scripts.

**Plan before execution**
   - For complex features: write a short plan (goal, phases, risks, affected modules) before coding.
   - Identify dependencies and blast radius using [code-review-graph.md](code-review-graph.md).

**Tests and behavior** — follow [testing-rules.md](testing-rules.md): RED → GREEN → IMPROVE.

**Review** — run [code-review-graph.md](code-review-graph.md) on your own diff; fix CRITICAL/HIGH findings.

**Local checks** — run focused tests during implementation. Before delivery, run
   the required full-tree Ruff and Mypy gates and the applicable full CI checks
   from [CI verification](ci-verification.md).

**Commit and release** — follow [git-commit-rules.md](git-commit-rules.md) and run the
   full CI gate in [ci-verification.md](ci-verification.md).
   - Branch up to date with main; no merge conflicts.
   - Only request review after the gate passes.

## Knowledge capture

- Project knowledge (architecture decisions, API changes, runbooks) goes into the project's docs structure.
- Do not duplicate information that already exists in docs or code comments.
- Ask before creating any new top-level documentation file.

## Relations

- Activates: any non-trivial feature or refactor. Orchestrates [testing-rules.md](testing-rules.md), [code-review-graph.md](code-review-graph.md), [git-commit-rules.md](git-commit-rules.md), and [security-rules.md](security-rules.md).
