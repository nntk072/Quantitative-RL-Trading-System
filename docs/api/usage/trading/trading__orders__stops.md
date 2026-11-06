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

1. [test fixture: `test_structural_stop_buffer_rounds_away_from_entry_to_price_grid`](../../../../tests/integration/backtest/test_entry_levels.py#L120)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_structural_stop_buffer_rounds_away_from_entry_to_price_grid(
    direction: int, reference: float, expected_stop: float
) -> None:
    menu, audit = stop_menu(
        _Menu([("custom_stop", reference)]),
        direction=direction,
        entry_price=100.0,
        row=_row(),
        min_dist=1.0,
        buffer=0.1,
        manipulation="none",
        htf=(),
        price_increment=0.25,
    )

    assert len(menu) == 1
    assert menu[0][:2] == ("custom_stop", expected_stop)
    assert menu[0][2] == pytest.approx(abs(100.0 - expected_stop))
    assert audit[0]["stop_price"] == pytest.approx(expected_stop)
```

2. [test fixture: `test_structural_stop_menu_rejects_invalid_price_increment`](../../../../tests/integration/backtest/test_entry_levels.py#L141)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_structural_stop_menu_rejects_invalid_price_increment(price_increment: float) -> None:
    with pytest.raises(ValueError, match="price_increment must be finite and positive"):
        stop_menu(
            _Menu([("custom_stop", 95.0)]),
            direction=1,
            entry_price=100.0,
            row=_row(),
            min_dist=1.0,
            buffer=0.0,
            manipulation="none",
            htf=(),
            price_increment=price_increment,
        )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
