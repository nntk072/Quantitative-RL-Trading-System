# Function to test reference map

`function_test_reference_map.csv` is a deterministic static inventory generated
from the current production Python tree. It includes **613**
source files, **3567** function, async-function, and class definitions,
of which **965** have at least one statically visible direct test
reference. Risk-tier row counts: P0 **1355**, P1 **2083**,
P2 **129**.

Name-based visibility counts: public **1987**, internal
**1580**. These follow leading-underscore naming
conventions; they do not establish the supported public API. Direct static test
reference counts by risk tier: P0 **421/1355**,
P1 **511/2083**, P2
**33/129**.

## Meaning of a reference

The generator detects Python `import` / `from ... import ...` statements in
`tests/test_*.py`, exact symbol imports, statically visible module attribute
access, and simple explicit symbol re-exports in package `__init__.py` files.
It also follows a simple named variable assigned from one unambiguous
production-class constructor imported by that file; this links instance method
references such as `env.step` to their class definition. It does not resolve
dynamic imports, runtime dispatch, fixture return types, or generated tests. A
listed test may import a symbol without calling it; an unlisted test can still
exercise it through a fixture or higher-level path. This is a navigation aid
only.

Every CSV row has `evidence_status=static_reference_only`. The `domain` column
is a semantic source-owner area, not a named maintainer. The production and
test reference columns list imports or statically visible module attribute
paths; neither is a call graph. Missing references do not prove that code is
unused or untested. The map does not claim that a test was run, that an
assertion is meaningful, that a branch was covered, or that behavior is
correct. Test/source SHA-256 columns pin the exact bytes inspected for each
static test reference. Rebuild it after source or test changes with:

```bash
.venv/bin/python scripts/research/analysis/evidence/build_function_test_reference_map.py
```

Use the architecture-matched repository environment when running this command.

## Package review views

`package_reference_summary.csv` groups definitions by their source directory
and reports direct static test-reference counts, with P0 totals broken out.
`priority_symbols_without_direct_test_references.csv` lists P0 definitions
that the static scan did not connect to a test and includes statically visible
production references where available. These are audit queues, not coverage
claims: indirect test paths, generated tests, runtime dispatch, and assertion
quality are not resolved. Review the prioritized rows against source and
behavior evidence before deciding whether code is dead or needs a contract.
`package_dependency_edges.csv` aggregates statically visible production
references between source directories. It omits intra-package references and
cannot represent dynamic imports, dependency inversion, or runtime call flow.

Production files are discovered recursively while excluding tests, orchestra,
virtual environments, build outputs, package installations, and bytecode
caches. The risk tier is a coarse review priority, not a severity score:

- **P0:** data, features, decisioning, simulation, trading, live and broker
  integration code, plus feature/data analysis tools.
- **P1:** model, learning, training, experiments, evaluation, artifact,
  configuration, compute, and evidence analysis code.
- **P2:** remaining support/documentation modules.

The source path and risk tier should be reviewed when new top-level domains or
analysis subdomains are added. Do not substitute this map for targeted
behavioral contracts, the release test gate, or a measured coverage report.
