# QA: Observations and masks

- **Status:** passed
- **Reviewer:** `qa_engineer`
- **Source revision:** `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` plus current working tree
- **Date:** 2026-11-15

## Source claims

| Claim checked against current hub | Source | Result |
|---|---|---|
| Sequence retains latest rows and left-pads short input | `decisioning/observations.py::pad_observation_window` | PASS |
| Sequence mask distinguishes real rows and empty input from padding | `decisioning/observations.py::pad_observation_window` | PASS |
| Non-finite values become zero with optional per-cell validity | `simulation/environment/observations.py::prepare_observation_feature_channels` | PASS |
| Runtime has `seq`, `seq_mask`, `account`, and configured branches | `simulation/environment/observation_runtime.py` | PASS |
| Disabled completed HTF history zeros branch and mask; candidate slot zero is eligible | `simulation/environment/observation_runtime.py`; `simulation/environment/candidate_geometry_observation.py` | PASS |

## Artifact and structure

`examples/observations-and-masks.ipynb` declares Tier A, CPU, deterministic synthetic arrays, and forced execution. Both code cells have saved execution counts (1, 2), two stream outputs, and no error output. Saved output shows a `(4, 4)` window with row mask `[0, 0, 1, 1]`. The hub has 178 lines, all 11 required sections, its notebook and contract reference, and 10/10 resolving Markdown links.

## Evidence limit

Saved arrays show mask examples, not a fresh run, a measured runtime, live data validity, checkpoint loading, or policy quality.
