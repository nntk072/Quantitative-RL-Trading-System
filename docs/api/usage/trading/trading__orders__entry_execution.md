# Trading · `orders.entry_execution`

This page contains 2 public callable records owned by `trading.orders.entry_execution`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `limit_order_expiry`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.entry_execution`

**Purpose:** Return the inclusive expiry timestamp for an M1-bar TTL.

**Exact API:** {py:obj}`trading.orders.entry_execution.limit_order_expiry` · **Source:** [trading/orders/entry_execution.py:51](../../../../trading/orders/entry_execution.py#L51)

**Inputs and outputs:**

- **Args:**

  ```text
  submission_time: Time the limit order became active.
  ttl_bars: Number of bar durations for which the order remains valid.
  bar_duration: Duration represented by one TTL bar.
  ```

- **Returns:**

  ```text
  Time at which the order's final eligible bar expires.
  ```

**Observed usage:**

1. [test fixture: `test_limit_order_expiry_uses_inclusive_bar_ttl`](../../../../tests/unit/trading/test_entry_execution_orders.py#L49)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_limit_order_expiry_uses_inclusive_bar_ttl() -> None:
    submitted = pd.Timestamp("2025-01-06 16:31:00", tz="UTC")

    expiry = limit_order_expiry(submitted, 5, pd.Timedelta(minutes=1))

    assert expiry == submitted + pd.Timedelta(minutes=5)
```

2. [test fixture: `test_limit_order_expiry_rejects_invalid_ttl_or_bar_duration`](../../../../tests/unit/trading/test_entry_execution_orders.py#L62)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_limit_order_expiry_rejects_invalid_ttl_or_bar_duration(
    ttl: int, duration: pd.Timedelta
) -> None:
    with pytest.raises(ValueError):
        limit_order_expiry(pd.Timestamp("2025-01-06 16:31:00", tz="UTC"), ttl, duration)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `limit_price_from_atr_offset`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.entry_execution`

**Purpose:** Place a passive limit from the decision close and round by trade side.

**Exact API:** {py:obj}`trading.orders.entry_execution.limit_price_from_atr_offset` · **Source:** [trading/orders/entry_execution.py:10](../../../../trading/orders/entry_execution.py#L10)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Trade direction, ``1`` for long or ``-1`` for short.
  reference_price: Causal close price used to place the order.
  atr: Current average true range in price units.
  offset_atr: Distance from the reference price, measured in ATR units.
  point_size: Minimum tradable price increment.
  ```

- **Returns:**

  ```text
  Passive limit price rounded to the instrument's price grid.
  ```

**Observed usage:**

1. [test fixture: `test_limit_price_uses_directional_atr_offset_and_tick_rounding`](../../../../tests/unit/trading/test_entry_execution_orders.py#L16)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_limit_price_uses_directional_atr_offset_and_tick_rounding(
    direction: int, expected: float
) -> None:
    price = limit_price_from_atr_offset(
        direction=direction,
        reference_price=100.0,
        atr=2.0,
        offset_atr=0.25,
        point_size=0.5,
    )

    assert price == pytest.approx(expected)
```

2. [test fixture: `test_limit_price_rounds_long_down_and_short_up`](../../../../tests/unit/trading/test_entry_execution_orders.py#L35)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_limit_price_rounds_long_down_and_short_up(
    direction: int, raw_price: float, expected: float
) -> None:
    reference = raw_price + direction * 0.0
    price = limit_price_from_atr_offset(
        direction=direction,
        reference_price=reference,
        atr=1.0,
        offset_atr=0.0,
        point_size=0.5,
    )

    assert price == pytest.approx(expected)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
