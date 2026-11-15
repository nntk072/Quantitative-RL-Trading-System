# QA: Swings, liquidity, SMT, PO3, FVG, and IFVG

- **Status:** passed
- **Reviewer:** `qa_engineer`
- **Source revision:** `c0d982f94ab9df8b2a9ddd013d2ae9a562573529` plus current working tree
- **Date:** 2026-11-15

## Source claims

| Claim checked against current hub | Source | Result |
|---|---|---|
| Pivot event waits for right-side bars and retains location | `features/technical/swings.py::detect_pivots` | PASS |
| Sweep uses prior confirmed level and ATR distance cap | `features/context/liquidity.py::detect_liquidity_sweeps`; `_detect_side_sweeps` | PASS |
| Secondary SMT confirmation projects to first primary row at or after it | `features/context/smt.py::smt_divergence` | PASS |
| Sweep arms PO3 manipulation; prior running extreme gates distribution | `features/po3/po3_phase_state.py::build_po3_state` | PASS |
| FVG uses three bars; IFVG requires zone pass and later close | `features/po3/fvg_detection.py::detect_fvg`; `features/po3/ifvg_detection.py::_detect_ifvg_confirmation_outputs` | PASS |

## Artifact and structure

`examples/swings-liquidity-smt-po3-fvg-ifvg.ipynb` declares Tier A, CPU, bundled/deterministic data, and forced execution. Its code cell has saved execution count 1, one result output, and no error output. Saved output shows pivot location 2 emitted on row 3 and a bullish gap on row 2. The hub has 153 lines, all 11 required sections, its notebook toctree and contract, and 9/9 resolving Markdown links; the cross-area causality guide link resolves.

## Evidence limit

The notebook checks only pivot and FVG timing, not SMT, sweep, PO3, or IFVG. Saved output does not prove a fresh run, runtime, predictive value, or tradability.
