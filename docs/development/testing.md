# Testing strategy

Tests are organized by what they exercise and where the behavior is owned:

| Location | Purpose |
|---|---|
| `tests/unit/<package>/` | Deterministic behavior inside one production package. |
| `tests/integration/` | Workflows across package boundaries and controlled I/O. |
| `tests/architecture/` | Dependency direction, public interfaces, repository layout, and documentation contracts. |
| `tests/research/` | Evidence protocols and research checks that are separate from normal PR gates. |
| `tests/fixtures/` | Small reusable inputs whose meaning is shared across tests. |

Execution markers are assigned from test paths by `tests/conftest.py`. Keep
that ownership model; do not add explicit `unit` or `integration` decorators
when the file location already supplies the marker. Add cost or environment
markers such as `slow`, `gpu`, or `triton` when they change how a case can run.

## Local gates

Run the narrowest relevant gate while editing:

```bash
./tools/check unit
./tools/check integration
./tools/check contracts
./tools/check parity
```

The normal PR workflow runs unit and integration tests once each, records
coverage contexts, combines the reports, and checks the combined results
against the committed baseline. To run both scoped suites with coverage locally:

```bash
./tools/check coverage
```

The test and coverage gates do not launch model training. Full repository
verification remains a CI or Orchestra phase 9 responsibility.

## Main-branch baseline

The initial measured baseline is from `main` at
`5a23e6321653c45719dfb8fdb831e242ff8c3d78`. It combines 1,998 unit and 242
non-slow integration cases. Pytest reported 280.85 seconds for unit tests and
36.49 seconds for integration tests in the reused GH200 allocation. GPU and
Triton markers were not part of this measurement.

| Measure | Main baseline |
|---|---:|
| Production Python files | 478 |
| Line coverage | 27,440 / 36,824 (74.52%) |
| Conditional branch coverage | 7,691 / 12,608 (61.00%) |
| Combined statement and branch coverage | 71.07% |

Exact package counts are stored in
[`tools/quality/coverage_baseline.json`](../../tools/quality/coverage_baseline.json).
The gate compares both line and branch ratios overall and for each production
package. When source additions make the baseline inappropriate, update it only
from a reviewed coverage run on `main` and retain the measurement scope and
commit provenance.

Coverage is a signal about execution, not proof that assertions protect the
behavior. Keep tests focused on observable contracts, edge cases, failure
handling, and invariants. Review uncovered branches in context instead of
adding tests solely to raise a percentage.

## Test overlap review

After collecting test-specific coverage contexts, run:

```bash
./tools/check test-overlap
```

The report ranks test-module pairs by shared production lines. Shared setup and
environment transitions can make unrelated tests look similar, so review the
assertions and behavior owner before consolidating anything. Keep tests in
separate modules when they protect different failure modes or contracts.

## Critical mutation checks

Run the bounded mutation suite with:

```bash
./tools/check mutation-critical
```

It mutates covered code in account limits, risk approval, action schemas,
walk-forward splitting, and timeframe alignment. These domains have direct
property or contract tests. The weekly GitHub workflow runs this command on
`main`; survivors are reviewed as missing assertions or equivalent mutations,
not converted automatically into a score threshold. The command uses four
workers by default; set `QRL_MUTATION_MAX_CHILDREN` to a positive integer when
the available CPU budget differs.
