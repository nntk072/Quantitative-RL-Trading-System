---
trigger: model_decision
description: "Use when designing or changing tests and selecting test scope."
---

# Testing rules

Applies to this repo's pytest setup (`tests/`).

## Coverage baseline

```bash
./tools/check unit
./tools/check coverage
```

The coverage gate measures line and conditional branch coverage for production
packages and compares it with the committed baseline from `main`. Do not claim
that percentage alone proves test quality. Review uncovered paths against the
behavior and failure modes the package owns. Run `./tools/check coverage` and
`./tools/check coverage-report` for the maintained gates.

Test types required for features:
1. **Unit tests** — production behavior at an isolated package boundary, under `tests/unit/<domain>/`.
2. **Integration tests** — interactions across packages and controlled I/O, under `tests/integration/`.
3. **Architecture tests** — package ownership, imports, and repository contracts under `tests/architecture/`.
4. **Research tests** — evidence protocols and larger analysis checks under `tests/research/`.

## Advisory local quality tooling

Use `./tools/check local-quality --help` for opt-in coverage diff,
impacted-test, static analysis, semantic, mutation, and evidence commands.
The implementation and policy live in `tools/quality/local_checks/`.
Preserve the existing required gates and distinguish infrastructure errors,
missing tools, advisory findings, and measured success. Never lower an
existing baseline, add unjustified coverage exclusions, weaken assertions
or parity tolerances, or claim unexecuted hardware validation passed.
Impact planning is for fast feedback, not a replacement for full CI.
Historical debt and costly training/fuzz/mutation campaigns are separate
work; run only the scope authorized by the active task.

## Test-driven development (mandatory for new features)

1. Write the test first (RED) — it should FAIL.
2. Run it to confirm failure.
3. Write minimal implementation (GREEN).
4. Refactor (IMPROVE) while preserving meaningful assertions and the coverage
   baseline.

Fix the implementation, not the tests — unless the tests are wrong.

## Structure

- **AAA pattern**: Arrange → Act → Assert.
- **Descriptive names** explaining behavior:
  - `test_sweep_reward_penalizes_early_entry`
  - `test_env_raises_when_action_out_of_bounds`
- Name test modules and test functions after the production behavior or contract
  they verify. Do not name them after a plan, phase, work package, or test-suite
  category; the `tests/unit/`, `tests/integration/`, `tests/research/`, and
  `tests/architecture/` directories already express the suite category.
- Test observable behavior and public contracts. Avoid tests that only assert
  that a forwarding module re-exports the same object; test the owning behavior
  and remove redundant forwarding layers when no external contract requires them.
- Let `tests/conftest.py` assign `unit`, `integration`, `architecture`, or
  `research` from the file path. Add explicit markers for cost or environment
  requirements such as `slow`, `gpu`, or `triton`.

Do not add `unit` or `integration` markers to every test when its path already
supplies the execution category.

```python
@pytest.mark.slow
def test_expensive_deterministic_case(): ...

```

## Relations

- Activates: any new feature, bug fix, or change to `features/`, `trading/`, `simulation/`, or environment logic.
- Enforced at commit by [git-commit-rules.md](git-commit-rules.md); orchestrated by [core-execution.md](core-execution.md) and [validation-routing.md](validation-routing.md); test runs follow [token-efficient-shell.md](token-efficient-shell.md).
