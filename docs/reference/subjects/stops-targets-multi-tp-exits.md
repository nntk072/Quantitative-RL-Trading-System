# Stops, targets, and multi-TP contract

**Status:** draft
**Source of truth:** `trading/risk/sizing.py`; `trading/orders/selection.py`; `trading/positions/multi_tp.py`; `trading/execution/broker.py` at `c0d982f94ab9df8b2a9ddd013d2ae9a562573529`.

## Inputs and units

| Field | Unit | Meaning |
|---|---|---|
| `entry_price`, `sl_price`, `tp*_price` | Instrument price | Proposed or active level; direction determines valid ordering |
| `buffer_pts` | Price points | Added beyond the swing reference, not dollars |
| `rr_ratio` | Ratio | Target distance divided by entry-to-stop distance |
| `tp1_raw`–`tp3_raw` | Index or normalized action | Per-slot target-menu selection |
| `tp_lot_fractions` | Fractions | Allocations for active target slots |
| `tp_hit_mask` | Bit mask | Bits 0, 1, 2 record TP1, TP2, TP3 hits |
| `ema_runner_fraction` | Initial-size fraction | Caps a positive final target close; a zero computed close falls back to full remainder |

## Validation and transitions

- A long swing low must be below entry; a short swing high must be above entry (`trading/risk/sizing.py`).
- An empty target menu yields disabled selections; a nonempty menu with three disabled selections falls back to TP3 index zero (`trading/orders/selection.py`).
- Active long targets must ascend and active short targets descend (`trading/orders/selection.py`).
- A target leg is rounded to two decimals and capped by remaining size. A positive final close may reserve an EMA runner; a zero computed close instead closes the full remainder (`trading/positions/multi_tp.py`).
- Invalid remaining targets are disabled; no replacement price is invented (`trading/positions/multi_tp.py`).

See the [subject guide](../../subjects/C_trading_risk_execution/stops-targets-multi-tp-exits.md), [action schema](../action_schemas.md), and [risk and execution](../risk_and_execution.md). Market performance is **not measured** here.
