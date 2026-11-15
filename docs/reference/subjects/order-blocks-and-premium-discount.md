# Order blocks and premium/discount contract

**Status:** draft
**Source of truth:** `features/context/order_blocks.py`; `features/context/premium_discount.py`

## Purpose

This contract names the inputs, scalar outputs, diagnostic event ledger, and session-routed range context.

## Inputs

| Name | Type | Meaning | Validation |
|---|---|---|---|
| Bars | OHLC DataFrame | Ordered price bars with a datetime index | Required open/high/low/close columns; periods and age positive |
| Swing period | Integer | Confirmed structure lookback | Passed to `structure_levels` |
| Impulse threshold | Float | Minimum candle body in ATR units | Must be finite and nonnegative |
| ATR | Series | Volatility normalization input for PD distances | Aligned to bars; zero/NaN does not yield a finite normalized distance |
| Session clock | Timezone and session labels | Routes active ranges | Uses canonical session helper |

## Outputs

| Output | Meaning | Source |
|---|---|---|
| Active order-block state | Latest bullish and bearish zone projection, bounds, midpoint, age, distance, origin time | `build_order_block_features` |
| Retest state | Scalar confirmation fields for the selected zone | `build_order_block_features` |
| Event ledger | Per-zone retest history for diagnostics | `build_order_block_features_with_event_ledger` |
| PD flags | Session-specific premium/discount and direction context | `build_pd_context_features` |
| PD raw levels | Absolute session/day/week ranges for diagnostics/environment use | `PD_CONTEXT_RAW_COLUMNS` |

## Configuration and schemas

- Canonical feature configuration and schema selection are linked from the [feature catalog](../feature_catalog.md).
- Tests: `tests/unit/features/test_order_blocks.py`, `test_session_ohlc.py`, and `test_structure.py`.

## Errors and limits

- Zone parameters define code behavior and do not establish market efficacy.
- Raw range levels must remain separate from normalized observation columns as specified by the feature schema.
- The scalar projection and full event ledger are different outputs; use the ledger for multi-zone diagnostic analysis.
