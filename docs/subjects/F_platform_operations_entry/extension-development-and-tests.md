# Extension development and tests

**Status:** draft
**Use this when:** You are adding a feature, schema, encoder, metric, or adapter and need to choose the implementation boundary and test scope.

## Summary and use this when

Start at the package that owns the contract and trace the changed behavior
to its consumers. Put new configuration in the canonical schema when the
change needs a setting. Add focused tests where they can distinguish the
actual failure from a working implementation, then update the corresponding
guide or reference when public behavior changes.

Read the [contribution workflow](https://github.com/nntk072/Quantitative-RL-Trading-System/blob/c0d982f94ab9df8b2a9ddd013d2ae9a562573529/CONTRIBUTING.md) and
[testing strategy](../../development/testing.md) for repository procedures.

## Key terms

- [Availability time and prefix invariance](../../glossary.md)
- [Observation schema and action schema](../../glossary.md)
- [Training mask](../../glossary.md)
- [Artifact and lineage](../../glossary.md)

## Explanation

### Choose the seam that owns the behavior

| Extension | Ownership question | Maintained guide |
|---|---|---|
| Feature | Which source timestamps and training rows can it use? | [Add a feature](../../how-to/add_feature.md) |
| Encoder | What observation shapes, fields, and masks does it consume? | [Add an encoder](../../how-to/add_encoder.md) |
| Action schema | What stable meaning does the consumer assign to each output? | [Add an action schema](../../how-to/add_action_schema.md) |
| Reward | Which environment event and units produce each term? | [Add a reward](../../how-to/add_reward.md) |
| Metric | Which ledger fields, filters, units and estimand does it require? | [Add a metric](../../how-to/add_metric.md) |
| Broker adapter | Which external fields map into broker-neutral contracts? | [Add a broker adapter](../../how-to/add_broker_adapter.md) |

When modifying existing code, inspect both the producer and consumer. A
different observation order can affect a saved policy with the same input
shape. The [schema version change guide](../../how-to/schema_version_change.md)
covers documenting and testing compatibility.

Keep runtime configuration rooted in `config/base/default.yaml` and cover
invalid input at load boundaries. A feature change can alter the meaning of
cached values even if the cache filename or machine stays the same. Review
the [cache identity guide](../A_data_features/cache-identity.md) for
content identity requirements.

### Test the claimed behavior

Use a fixture small enough to inspect by hand. For causal alignment, put a
higher-timeframe close inside the lower-timeframe index and examine all
three relevant rows: just before close, exactly at close, and once after.
Compare the common prefix while adding an unrelated future observation.
This exposes timing regressions even when frame dimensions stay constant.

Use unit tests for isolated package behavior, integration tests for behavior
across contracts and controlled I/O, and architecture tests for package and
repository rules. Put evidence-protocol checks that need their own scheduling
in the research suite. Label expensive tests according to their actual
execution needs.

`tests/conftest.py` assigns a suite marker by test path when a case lacks a
recognized execution marker. Existing markers in the declared execution set
suppress that assignment. Consider the named gate's selection expression
when applying an explicit execution marker.

### Change documentation at the same boundary

Use code docstrings for public callable signatures and failure conditions.
Use the maintained subject/reference guide for behavior that callers need
to recognize across packages, and a runbook for operational procedures.
Keep a new example deterministic and small enough to run on the documented
hardware tier. Update generated indexes through the maintained procedure
when the documentation change is integrated.

### Failure modes

- Introducing a new import from a workflow package into a lower-level
  contract can create a dependency cycle.
- Reimplementing an action mapping in a downstream adapter can diverge
  from canonical schema order.
- Checking a feature value only after a bar closes misses early-availability
  regressions.
- Adding an expensive marker without reading gate selection can put a test
  outside the suite selected for a PR.
- Reusing a smoke output as a performance result skips the evidence protocol.

## Worked example

The Tier A notebook runs `align_timeframes` on M1 and M5 fixtures with an
explicit M5 availability time. It asserts that the completed value is
missing before the close, visible at the close, and carried forward on
later M1 rows. An appended future M5 close leaves those rows unchanged.

```{toctree}
:hidden:

examples/extension-development-and-tests
```

## Tasks

- Read the relevant [how-to workflow](../../how-to/README.md) before changing
  a public extension point.
- Use [module guides](../../modules/README.md) to locate package ownership
  and public contracts.
- Use the [testing strategy](../../development/testing.md) to choose the
  test scope and targeted gate.
- Use the [documentation policy](../../development/documentation.md) for
  code, guides, notebook metadata, and inventory updates.
- Read the [development and tests reference](../../reference/subjects/extension-development-and-tests.md)
  for path-based markers and gate selection.

## Contract

| Item | Contract | Source |
|---|---|---|
| New settings | Begin with canonical runtime defaults and trace the resolved config | `config/base/default.yaml` |
| Code boundaries | Keep direction, public cross-domain imports, and package isolation | `tests/architecture/test_dependency_rules.py` |
| Causal alignment | Explicit close availability followed by forward alignment | `market_data/transforms/align.py::align_timeframes` |
| Execution markers | Suite by path when recognized markers are absent | `tests/conftest.py::execution_markers_for_test` |
| Named checks | Separate architecture, contract, unit, integration, and docs routes | `tools/check` |
| Tier A notebook | Metadata and CPU execution policy are checked | `tools/documentation/check_notebooks.py` |

## Verify

- `tests/architecture/test_dependency_rules.py` covers allowed directions,
  public cross-domain imports, and cycle detection.
- `tests/architecture/test_test_execution_markers.py` checks classification
  and named gate expressions.
- `tests/unit/features/test_htf_alignment.py` checks completed-bar alignment
  including explicit close times for shortened bars.
- `tests/architecture/test_documentation_contracts.py` covers maintained
  documentation contract checks.

## Limits and common mistakes

A unit case establishes behavior for its fixture and assertions. A passing CI
gate establishes the scope it selected. Economic performance, deployment
readiness, and cluster behavior need separate evidence.

If a test fixture depends on a previously built cache or local broker
installation, document the integration requirement and keep isolated
contract tests independently runnable.

## Change checklist

- Trace callers, persisted inputs, and failure handling before editing.
- Test representative success, boundary, and failure cases.
- Review configuration provenance and schema compatibility.
- Verify the selected suite runs the intended case.
- Update maintained reader material and generated documentation as required.
- Record only the gates actually run and their observed outcomes.

## Maintainer note

- Verified commit: `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`
- Verified date: 2026-11-15
- Owner: `architect`
