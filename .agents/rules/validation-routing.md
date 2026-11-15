---
trigger: model_decision
description: "Use to choose checks by change scope and risk without repeating full gates."
---

# Validation routing

Validation follows changed contracts and dependencies, not a fixed checklist
for every edit.

1. During implementation, run the smallest focused tests and non-mutating
   format/lint checks for the changed behavior.
2. After integration, run affected producer/consumer tests, architecture
   checks, and generated-doc/API checks where relevant. Do not run duplicate
   copies of the same suite.
3. Before an authorized commit, preserve the required full-tree gates:
   `.venv-arm/bin/ruff format --check .`, `.venv-arm/bin/ruff check .`,
   `.venv-x86/bin/python -m mypy .` on x86 or `.venv-arm/bin/python -m mypy .` on ARM,
   and relevant scoped pytest. Use the architecture-matched environment.
   Never replace full-tree Ruff/Mypy with
   path-scoped forms at commit time.
4. Run `./tools/check full` only when requested, in its designated release/CI
   workflow, or to reproduce a complete hosted failure.
5. Report commands actually run, counts, failures, and limitations. Do not
   claim a check passed when it was skipped or inferred.
6. For agent-system changes, run `tools/agent/validate-rules`,
   `.venv-x86/bin/python tools/agent/validate-profiles`, and
   `.venv-x86/bin/python -m pytest tests/unit/tooling/test_agent_architecture.py -q` on
   x86; use `.venv-arm/bin/python` on ARM.
   Run `extension-doctor` or `context-status` when their reported state matters.

For CI path/job mapping and commit ownership use `ci-verification.md` and
`git-commit-rules.md`. For test design use `testing-rules.md`.
