# Repository tools

`tools/` contains developer-facing checks and setup helpers. These tools
validate or prepare the repository; they are not part of policy inference,
market simulation, or trading behavior.

The main entrypoint is `./tools/check`, which dispatches named verification
gates. `tools/documentation/` validates maintained links, package guide
coverage, and generated architecture references. Environment setup helpers
select architecture-appropriate Python environments. Read a tool's `--help`
or source before using an operation that writes files.

`./tools/check coverage` runs the scoped unit and integration gates with
coverage enabled. In CI those suites publish their coverage data once, and
`./tools/check coverage-report` combines the data, emits XML/JSON reports, and
checks line coverage against the measured `main` baseline. Branch coverage is
reported but does not fail the gate.

`./tools/check test-overlap` ranks test modules by the production lines their
coverage contexts share. Use the results to choose pairs for source-and-assertion
review; overlap alone is not evidence that two tests protect the same contract.

`./tools/check mutation-critical` runs the curated mutation set for account risk,
action coordinates, walk-forward folds, and timeframe alignment. The scheduled
workflow runs it from `main`; results are a focused test-quality signal, not a
repository-wide mutation score. It uses four workers by default; set
`QRL_MUTATION_MAX_CHILDREN` to a positive integer to change the cap.

See the [testing rules](../.agents/rules/testing-rules.md),
[documentation checks](documentation/check_docs.py), and the
[agent verification rules](../.agents/rules/ci-verification.md).
