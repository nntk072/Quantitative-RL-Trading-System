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

**Observed usage:**

1. [test fixture: `test_deviation_levels_require_a_finite_positive_swing_range`](../../../../tests/unit/trading/test_order_level_geometry.py#L24)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_deviation_levels_require_a_finite_positive_swing_range(
    swing_low: float, swing_high: float
) -> None:
    assert deviation_levels(swing_low, swing_high, 99.0, 111.0) == []
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

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

1. [test fixture: `test_candle_proximity_uses_half_span_padding_and_rejects_nonfinite_levels`](../../../../tests/unit/trading/test_order_level_geometry.py#L11)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_candle_proximity_uses_half_span_padding_and_rejects_nonfinite_levels() -> None:
    assert level_near_candles(8.0, 10.0, 14.0)
    assert not level_near_candles(7.99, 10.0, 14.0)
    assert not level_near_candles(float("nan"), 10.0, 14.0)
    assert not level_near_candles(12.0, 10.0, float("inf"))
```

2. [production caller: `deviation_levels`](../../../../trading/orders/levels.py#L51)

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

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
