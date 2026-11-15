# QA: Action schemas and parameterization

- **Status:** passed
- **Reviewer:** `qa_engineer`
- **Source revision:** `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` plus current working tree
- **Date:** 2026-11-15

## Source claims

| Claim checked against current hub | Source | Result |
|---|---|---|
| Base overlay order and optional controls | `decisioning/actions.py::build_action_schema` | PASS |
| Simplex requires multiple targets | `decisioning/actions.py::build_action_schema` | PASS |
| Setup layout adds entry-execution coordinates and version | `decisioning/trade_setup.py::build_trade_setup_action_schema` | PASS |
| Config rejects entry execution without setup actions | `decisioning/actions.py::build_action_schema_from_config` | PASS |
| Discrete menu is hold, 18 entries, exit | `decisioning/actions.py::build_discrete_trading_action_schema` | PASS |

## Artifact and structure

`examples/action-schemas-and-parameterization.ipynb` declares Tier A, CPU, deterministic schema-only data, and forced execution. Both code cells have saved execution counts (1, 2), two stream outputs, and no error output. Saved values show two width-six layouts with different names and a 12-coordinate entry-execution layout. The hub has 172 lines, all 11 required sections, its notebook and contract reference, and 10/10 resolving Markdown links.

## Evidence limit

Saved outputs demonstrate schema mechanics, not a fresh run, a measured runtime, checkpoint compatibility, or policy quality.
