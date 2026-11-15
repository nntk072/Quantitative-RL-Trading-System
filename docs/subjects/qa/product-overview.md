# QA for product overview

**Status:** Five source claims verified at
`c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.

## Source claims

1. `pyproject.toml` declares `quantitative-rl-trading-system`, Python
   `>=3.12`, and six console scripts. The script map agrees with
   `tests/architecture/test_project_identity.py`.
2. `market_data/cli.py::main` accepts `prepare`, `discover`, and
   `prebuild-experiment-run-cache`. `evaluation/cli.py::main` accepts
   `reanalyze` and routes it to checkpoint reanalysis.
3. `training/cli.py::main` recognizes five first-token commands and
   passes the original argument list to the train parser in the fallback.
   This also covers the unqualified `--help` route.
4. The eight experiment commands and four compute commands in the
   reference match `experiments/cli.py::main` and `compute/cli.py::main`.
   `tests/architecture/test_public_imports.py` checks stable CLI imports
   and inclusion of top-level packages in the wheel.
5. `AGENTS.md` identifies `config/base/default.yaml` as the defaults
   owner. `docs/research/validation_protocol.md` governs chronological
   evaluation and the interpretation of exposed periods.

## Document and notebook checks

The hub has 167 lines and the title and ten required sections. Its 17
local links, the reference's four local links, and the notebook toctree
target resolve to files. The reference's dispatch table agrees with source.

Static notebook metadata and schema checks accepted Tier A, CPU, bundled
deterministic expectations, subject, owner, Python 3 kernel, the declared
under-60-seconds target, and forced MyST execution. The metadata title
matches the first Markdown heading. One assert-bearing code cell has
execution count 1, one saved result with the six expected routes, and
zero saved errors. Recorded cell time is 0.009 seconds.

## Evidence limit

The example compares expected targets with the installed distribution's
metadata. It provides package registration evidence. Its stored output
contains no runtime, economic, or deployment measurements. QA inspected the
saved result without executing the notebook or launching a workflow.
