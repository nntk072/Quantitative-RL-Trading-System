# Trading · `orders.stops`

This page contains 3 public callable records owned by `trading.orders.stops`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `filter_sl_candidates`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.stops`

**Purpose:** Keep SL levels on the correct side and at least ``min_dist`` away.

**Exact API:** {py:obj}`trading.orders.stops.filter_sl_candidates` · **Source:** [trading/orders/stops.py:76](../../../../trading/orders/stops.py#L76)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  entry_price: Price at which the position was opened.
  candidates: Items supplied for the candidates, in input order.
  min_dist: Numeric value used for the min dist.
  ```

- **Returns:**

  ```text
  Values returned by ``filter_sl_candidates``, in the declared order.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = filter_sl_candidates(direction=..., entry_price=..., candidates=..., min_dist=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `manipulation_state`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.stops`

**Purpose:** Return the PO3 manipulation state that filters structural stops.

**Exact API:** {py:obj}`trading.orders.stops.manipulation_state` · **Source:** [trading/orders/stops.py:48](../../../../trading/orders/stops.py#L48)

**Inputs and outputs:**

- **Args:**

  ```text
  row: Row index or record being processed.
  ```

- **Returns:**

  ```text
  Text returned by ``manipulation_state``.
  ```

**Observed usage:**

1. [production caller: `place_strategy_order`](../../../../trading/orders/entries.py#L270)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        standard_deviation_timeframes = (
            (str(trade_setup.setup_timeframe),)
            if str(trade_setup.idea) == "standard_deviation"
            else None
        )
    state = manipulation_state(feat_row)
    buf = stop_buffer(buffer_pts)
    stops, stop_audit = stop_menu(
        strategy,
        direction=direction,
        entry_price=float(entry_price),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `stop_menu`

**Kind:** function · **Status:** stable · **Owner:** `trading.orders.stops`

**Purpose:** Build structural stops and audit every rejected level.

**Exact API:** {py:obj}`trading.orders.stops.stop_menu` · **Source:** [trading/orders/stops.py:107](../../../../trading/orders/stops.py#L107)

**Inputs and outputs:**

- **Args:**

  ```text
  strategy: Strategy used to select or evaluate trades.
  direction: Signed trade direction: 1 for long and -1 for short.
  entry_price: Price at which the position was opened.
  row: Row index or record being processed.
  min_dist: Numeric value used for the min dist.
  buffer: Numeric value used for the buffer.
  manipulation: Text or path value identifying the manipulation.
  htf: Items supplied for the htf, in input order.
  min_timeframe: Text or path value identifying the min timeframe.
  standard_deviation_timeframes: Items supplied for the standard deviation timeframes, in input order.
  price_increment: Price increment used by the operation described above.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any]]`` values.
  ```

**Observed usage:**

1. [test fixture: `test_session_extremes_are_structural_order_candidates`](../../../../tests/integration/backtest/test_entry_levels.py#L136)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_session_extremes_are_structural_order_candidates(
    direction: int, expected_stops: set[str], expected_targets: set[str]
) -> None:
    row = _row(london_low=95.0, asian_low=94.0, london_high=105.0, asian_high=106.0)

    menu, _audit = stop_menu(
        BaselineStrategy(),
        direction=direction,
        entry_price=100.0,
        row=row,
        min_dist=1.0,
        buffer=0.0,
        manipulation="none",
        htf=(),
    )

    stop_names = {part for name, _stop, _distance in menu for part in name.split("|")}
    assert expected_stops <= stop_names
    targets = target_menu(
        direction=direction,
# … caller assertions omitted …
```

2. [test fixture: `test_stop_menu_applies_h2_floor_and_keeps_weekly_references`](../../../../tests/integration/backtest/test_entry_levels.py#L215)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        M15_last_swing_low=95.0,
        H2_last_swing_low=90.0,
        W1_last_swing_low=80.0,
    )

    menu, _audit = stop_menu(
        BaselineStrategy(),
        direction=1,
        entry_price=100.0,
        row=row,
        min_dist=1.0,
        buffer=0.0,
        manipulation="none",
        htf=("M15", "H2", "W1"),
        min_timeframe="H2",
    )

    names = {part for name, _stop, _distance in menu for part in name.split("|")}
    assert "M15_last_swing_low" not in names
    assert {"H2_last_swing_low", "W1_last_swing_low"} <= names
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
