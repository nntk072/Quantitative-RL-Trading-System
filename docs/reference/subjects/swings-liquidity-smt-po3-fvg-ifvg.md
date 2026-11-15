# Swings, liquidity, SMT, PO3, FVG, and IFVG contract

**Status:** draft
**Source of truth:** `features/technical/swings.py`, `features/context/liquidity.py`, `features/context/smt.py`, `features/po3/`

## Purpose

This reference records event timing and output distinctions for the market-structure feature family. Implementation and resolved configuration are authoritative.

## Inputs

| Name | Type | Meaning | Validation or timing |
|---|---|---|---|
| Bars | OHLC DataFrame | Chronological prices indexed by source time | Pivot and FVG routines require relevant high/low/close columns |
| Right window | Integer | Bars needed after a pivot | Event appears on confirmation row |
| ATR | Series | Reversal/overshoot scale | Values are consumed at the candidate/event row |
| Secondary bars | OHLC DataFrame | Paired instrument source observations | Secondary pivots use observed rows, not forward-filled synthetic rows |

## Outputs

| Output | Meaning | Source |
|---|---|---|
| Pivot | Event, price, extreme, original location | `detect_pivots` |
| Swing | Accepted event and carried level fields | `detect_swings` |
| Sweep | Event, level, wick, reclaim, age | `detect_liquidity_sweeps` |
| SMT | Paired-symbol divergence and aligned close context | `smt_divergence` |
| FVG / IFVG | Gap-zone and later confirmation features | `detect_fvg`; `detect_ifvg_confirmation` |

## Configuration and schemas

- Defaults and selected columns are defined in the feature code/configuration and listed in the [feature catalog](../feature_catalog.md).
- Test contracts: `tests/unit/features/test_pivots_swings.py`, `test_liquidity.py`, `test_smt.py`, and `test_po3_ifvg_state.py`.

## Errors and limits

- The documented outputs are software features, not evidence of trade performance.
- Higher-timeframe availability follows source-bar close semantics; never backfill a future confirmation.
- Parameter changes alter the operational definitions and require focused tests and cache-identity review.
