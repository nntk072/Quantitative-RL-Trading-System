# Trading · `orders.levels`

This page contains 2 public callable records owned by `trading.orders.levels`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `deviation_levels`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.levels`

**Purpose:** Find projected levels extended from the latest candle around a swing range.

**Exact API:** {py:obj}`trading.orders.levels.deviation_levels` · **Source:** [trading/orders/levels.py:29](../../../../trading/orders/levels.py#L29)

**Inputs and outputs:**

- **Args:**

  ```text
  swing_low: Low endpoint of the measured swing.
  swing_high: High endpoint of the measured swing.
  candle_lo: Low of the candle used for proximity checks.
  candle_hi: High of the candle used for proximity checks.
  ```

- **Returns:**

  ```text
  Eligible projected prices in configured order.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = deviation_levels(swing_low=..., swing_high=..., candle_lo=..., candle_hi=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `level_near_candles`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.levels`

**Purpose:** Return whether a price level is within a padded candle range.

**Exact API:** {py:obj}`trading.orders.levels.level_near_candles` · **Source:** [trading/orders/levels.py:8](../../../../trading/orders/levels.py#L8)

**Inputs and outputs:**

- **Args:**

  ```text
  price: Price level being tested.
  candle_lo: Candle low.
  candle_hi: Candle high.
  pad_frac: Padding as a fraction of candle height.
  ```

- **Returns:**

  ```text
  True when the level is inside the padded range.
  ```

**Observed usage:**

1. [production caller: `deviation_levels`](../../../../trading/orders/levels.py#L51)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def deviation_levels(
    swing_low: float, swing_high: float, candle_lo: float, candle_hi: float
) -> list[tuple[float, float]]:
    if not np.isfinite(swing_low) or not np.isfinite(swing_high):
        return []
    span = float(swing_high) - float(swing_low)
    if span <= 0.0:
        return []
    out: list[tuple[float, float]] = []
    for k in DEVIATION_KS:
        price = float(swing_low) + float(k) * span
        if level_near_candles(price, candle_lo, candle_hi):
            out.append((float(k), price))
    return out
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
