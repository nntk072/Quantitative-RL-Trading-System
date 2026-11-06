# Trading · `orders.targets`

This page contains 3 public callable records owned by `trading.orders.targets`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `collapse_levels`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.targets`

**Purpose:** Merge prices within ``1e-4`` and join their names with ``|``.

**Exact API:** {py:obj}`trading.orders.targets.collapse_levels` · **Source:** [trading/orders/targets.py:20](../../../../trading/orders/targets.py#L20)

**Inputs and outputs:**

- **Args:**

  ```text
  items: Items supplied for the items, in input order.
  price_increment: Price increment used by the operation described above.
  ```

- **Returns:**

  ```text
  Values returned by ``collapse_levels``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_equal_prices_collapse_and_distinct_prices_stay`](../../../../tests/integration/backtest/test_entry_levels.py#L92)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_equal_prices_collapse_and_distinct_prices_stay() -> None:
    one = collapse_levels(
        [
            ("last_swing_high", 100.0),
            ("london_high", 100.0 + 1e-5),
            ("prev_day_high", 100.0),
            ("sweep_high_level", 100.00005),
        ]
    )
    assert len(one) == 1
    assert one[0][0] == "last_swing_high|london_high|prev_day_high|sweep_high_level"
    two = collapse_levels([("a", 100.0), ("b", 110.0)])
    assert len(two) == 2
```

2. [test fixture: `test_levels_collapse_at_configured_instrument_precision`](../../../../tests/integration/backtest/test_entry_levels.py#L107)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_levels_collapse_at_configured_instrument_precision() -> None:
    assert collapse_levels(
        [("first", 100.0), ("same_tick", 100.004), ("next_tick", 100.006)],
        price_increment=0.01,
    ) == [("first|same_tick", 100.0), ("next_tick", 100.006)]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `deviation_candidates`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.targets`

**Purpose:** Use extensions of already-created swing legs as TP levels.

**Exact API:** {py:obj}`trading.orders.targets.deviation_candidates` · **Source:** [trading/orders/targets.py:212](../../../../trading/orders/targets.py#L212)

**Inputs and outputs:**

- **Args:**

  ```text
  row: Row index or record being processed.
  allow_extreme_extension: Whether to enable or require the allow extreme extension.
  ```

- **Returns:**

  ```text
  Values returned by ``deviation_candidates``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_extreme_swing_extensions_are_tp_references_for_all_exit_modes`](../../../../tests/integration/backtest/test_entry_levels.py#L706)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "standard_deviation_level_neg_4_price",
        "standard_deviation_level_neg_6_price",
        "standard_deviation_level_neg_8_price",
    }
    # The shared candidate helper remains conservative for protective stops.
    assert deviation_candidates(row) == [("standard_deviation_level_neg_4_price", 106.0)]
```

2. [production caller: `stop_menu`](../../../../trading/orders/stops.py#L255)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        if column_name == ob_stem or column_name.endswith(f"_{ob_stem}"):
            if _flag(row, column_name.removesuffix("_low").removesuffix("_high") + "_active"):
                level = finite_level(row, column_name)
                if level is not None:
                    raw.append((column_name, level))
    raw.extend(deviation_candidates(row))
    raw_deviation_candidates = [item for item in raw if "standard_deviation_level_" in item[0]]
    invalid_deviation_candidates = [
        item
        for item in raw_deviation_candidates
        if not (
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `target_menu`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.targets`

**Purpose:** Build eligible take-profit prices from reward-risk and market-structure levels.

**Exact API:** {py:obj}`trading.orders.targets.target_menu` · **Source:** [trading/orders/targets.py:58](../../../../trading/orders/targets.py#L58)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Trade direction, positive for long and negative for short.
  entry_price: Proposed entry price.
  row: Current feature row containing structure levels.
  stop_dist: Stop distance in price units.
  max_tp_distance: Maximum permitted target distance.
  rr_bounds: Optional inclusive reward-risk bounds.
  htf: Higher timeframes whose structure levels may be considered.
  front_run_pts: Offset used to avoid placing targets directly on levels.
  price_increment: Optional instrument tick size.
  source_prices: Optional explicit source-level prices.
  min_timeframe: Optional minimum timeframe accepted for a target.
  ```

- **Returns:**

  ```text
  Ordered target candidates that pass direction and distance checks.
  ```

**Observed usage:**

1. [test fixture: `test_structural_menus_reject_invalid_trade_direction`](../../../../tests/integration/backtest/test_entry_levels.py#L169)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            buffer=0.0,
            manipulation="none",
            htf=(),
        )
    with pytest.raises(ValueError, match="direction must be -1 or 1"):
        target_menu(
            direction=direction,
            entry_price=100.0,
            row=_row(),
            stop_dist=1.0,
            max_tp_distance=float("nan"),
            htf=(),
        )
```

2. [test fixture: `test_structural_menus_reject_unknown_source_timeframe`](../../../../tests/integration/backtest/test_entry_levels.py#L193)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            manipulation="none",
            htf=("M99",),
        )

    with pytest.raises(ValueError):
        target_menu(
            direction=1,
            entry_price=100.0,
            row=_row(M99_last_swing_high=110.0),
            stop_dist=1.0,
            max_tp_distance=float("nan"),
            htf=("M99",),
        )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
