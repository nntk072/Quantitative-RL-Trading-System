# QA for extension development and tests

**Status:** Five source claims verified at
`c0d982f94ab9df8b2a9ddd013d2ae9a562573529`, with the notebook
checker changes scoped to the working tree.

## Source claims

1. `AGENTS.md` gives `config/base/default.yaml` ownership of defaults.
   `tools/check::run_contracts` runs the config typo-safety test together
   with explicit schema, artifact, cache, and fit-scope tests.
2. `tests/architecture/test_dependency_rules.py` asserts acyclic
   production imports, public cross-domain imports, and backend neutrality
   for evaluation and live.
3. `tests/conftest.py::execution_markers_for_test` resolves architecture,
   integration, research, and unit path precedence, raises for
   unclassified paths, and suppresses the suite marker when a recognized
   execution marker is present. The adjacent architecture marker test
   verifies classification and the named expressions.
4. `tools/check` selects the stated architecture, unit, integration,
   contract, and docs scopes. Its docs route includes notebook validation,
   generated documentation checks, and a warnings-as-errors Sphinx build.
5. `market_data/transforms/align.py::align_timeframes` indexes higher
   timeframe rows by supplied close timestamps and forward-aligns to M1.
   `tests/unit/features/test_htf_alignment.py` tests explicit closes for
   shortened bars and future-prefix invariance.

## Document and notebook checks

The 159-line hub has the title and ten required sections. Twenty local
links and one pinned Git-source link target resolve across the hub and
reference. The notebook toctree target exists. The reference's marker
precedence and gate scopes agree with the pinned implementation.
The working-tree notebook checker extends the pinned checker with data,
subject, and owner metadata validation and a 60-second runtime bound.

Static schema and notebook metadata checks accepted the Python 3 kernel,
Tier A, CPU, matching subject and owner, declared under-60-seconds target,
deterministic bundled data, forced MyST execution, and matching first
heading and title. The single assert-bearing code cell has count 1, one
saved result, and zero saved errors. The result shows a missing M5 value
before close and 100 at and after close. Recorded cell time is 8.582 seconds.

## Evidence limit

The saved result covers the fixed close-time fixture. The source cell
asserts prefix invariance after appending a future bar. QA inspected the
notebook and test sources without rerunning the notebook or test suites.
