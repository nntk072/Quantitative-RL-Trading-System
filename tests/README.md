# Tests

The test tree is organized around behavior and ownership. Tests protect
contracts and failure handling; they do not prove that a trading policy will
be profitable.

| Area | Typical coverage |
|---|---|
| `tests/architecture/` | Dependency direction, public boundaries, repository layout, and documentation contracts. |
| `tests/unit/` | Focused package behavior and deterministic edge cases. |
| `tests/unit/research/` | Research report, evidence, and frozen-run compatibility behavior. |
| `tests/integration/` | Cross-package pipelines and controlled I/O boundaries. |
| `tests/test_*` | Legacy and domain-oriented behavior suites being consolidated over time. |
| `tests/fixtures/` | Small reusable input data and fixtures shared by tests. |
| `tests/research/` | Larger evidence or protocol checks, not the default fast unit gate. |

Mark tests by cost and dependency (`unit`, `integration`, `architecture`,
`slow`, `gpu`, `triton`, or `research`). Keep fixtures close to the tests that
own their meaning; never put synthetic test-only records in reader-facing
research documentation.

For the current commands and gate policy, see
[CI verification](../.agents/rules/ci-verification.md) and
[Orchestra](../orchestra/README.md).
