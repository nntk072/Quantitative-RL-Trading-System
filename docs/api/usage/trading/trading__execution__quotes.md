# Trading · `execution.quotes`

This page contains 9 public callable records owned by `trading.execution.quotes`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `adverse_tick_fill_quote`

**Kind:** function · **Status:** stable · **Owner:** `trading.execution.quotes`

**Purpose:** Worsen only the transacted quote side by configured tick slippage.

**Exact API:** {py:obj}`trading.execution.quotes.adverse_tick_fill_quote` · **Source:** [trading/execution/quotes.py:10](../../../../trading/execution/quotes.py#L10)

**Inputs and outputs:**

- **Args:**

  ```text
  quote: Executable bid/ask pair.
  direction: Position side, +1 for long or -1 for short.
  slippage_points: Adverse price adjustment applied to the transacted side.
  opening: Whether the quote is used to open or close the position.
  ```

- **Returns:**

  ```text
  Adjusted bid/ask pair with the untouched side preserved.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = adverse_tick_fill_quote(quote=..., direction=..., slippage_points=..., opening=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `bar_stop_fill_quote`

**Kind:** function · **Status:** stable · **Owner:** `trading.execution.quotes`

**Purpose:** Price a bar stop at its level or at a worse opening quote.

**Exact API:** {py:obj}`trading.execution.quotes.bar_stop_fill_quote` · **Source:** [trading/execution/quotes.py:212](../../../../trading/execution/quotes.py#L212)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  stop_price: Numeric value used for the stop price.
  bar_open: Numeric value used for the bar open.
  raw_spread_points: Raw spread points used by the operation described above.
  cost_model: Cost model used by the operation described above.
  ```

- **Returns:**

  ```text
  Values returned by ``bar_stop_fill_quote``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_trading_quote_contract_owns_protective_and_bar_stop_fills`](../../../../tests/integration/backtest/test_engine_execution_contract.py#L70)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trading_quote_contract_owns_protective_and_bar_stop_fills() -> None:
    model = CostModel(spread_points=0.6, point_size=0.01, slippage_points=5.0)

    assert protective_level_fill_quote(1, 100.0, model) == (95.0, 95.6)
    assert protective_level_fill_quote(-1, 100.0, model) == (104.4, 105.0)
    assert bar_stop_fill_quote(1, 100.0, 98.0, 80.0, model) == (93.0, 93.6)
    assert bar_stop_fill_quote(-1, 100.0, 102.0, 80.0, model) == (107.2, 107.8)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `bar_stop_trigger_price`

**Kind:** function · **Status:** stable · **Owner:** `trading.execution.quotes`

**Purpose:** Account for a bar opening through its protective stop.

**Exact API:** {py:obj}`trading.execution.quotes.bar_stop_trigger_price` · **Source:** [trading/execution/quotes.py:189](../../../../trading/execution/quotes.py#L189)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  stop_price: Numeric value used for the stop price.
  bar_open: Numeric value used for the bar open.
  opening_spread: Numeric value used for the opening spread.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``bar_stop_trigger_price``.
  ```

**Observed usage:**

1. [production caller: `bar_stop_fill_quote`](../../../../trading/execution/quotes.py#L234)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def bar_stop_fill_quote(
    direction: int,
    stop_price: float,
    bar_open: float,
    raw_spread_points: float | None,
    cost_model: CostModel,
) -> tuple[float, float]:
    spread = raw_spread_to_price(raw_spread_points, cost_model.point_size)
    if spread is None:
        spread = float(cost_model.spread_points)
    trigger = bar_stop_trigger_price(direction, stop_price, bar_open, spread)
    return protective_level_fill_quote(direction, trigger, cost_model)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `exit_side_bar_range`

**Kind:** function · **Status:** stable · **Owner:** `trading.execution.quotes`

**Purpose:** Return low/high OHLC bounds on the position's executable exit side.

**Exact API:** {py:obj}`trading.execution.quotes.exit_side_bar_range` · **Source:** [trading/execution/quotes.py:135](../../../../trading/execution/quotes.py#L135)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Position direction, ``1`` for long or ``-1`` for short.
  bid_low: Low bid price from the bar.
  bid_high: High bid price from the bar.
  spread_price_units: Recorded spread converted to price units, or
      ``None`` to use the configured default spread.
  cost_model: Cost model providing the default spread when needed.
  ```

- **Returns:**

  ```text
  The low and high prices for the position's executable exit side.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = exit_side_bar_range(direction=..., bid_low=..., bid_high=..., spread_price_units=..., cost_model=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `protective_level_fill_quote`

**Kind:** function · **Status:** stable · **Owner:** `trading.execution.quotes`

**Purpose:** Build a bid/ask quote that executes a protective level with adverse slippage.

**Exact API:** {py:obj}`trading.execution.quotes.protective_level_fill_quote` · **Source:** [trading/execution/quotes.py:167](../../../../trading/execution/quotes.py#L167)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Signed trade direction: 1 for long and -1 for short.
  hit_price: Numeric value used for the hit price.
  cost_model: Cost model used by the operation described above.
  ```

- **Returns:**

  ```text
  Values returned by ``protective_level_fill_quote``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_trading_quote_contract_owns_protective_and_bar_stop_fills`](../../../../tests/integration/backtest/test_engine_execution_contract.py#L68)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trading_quote_contract_owns_protective_and_bar_stop_fills() -> None:
    model = CostModel(spread_points=0.6, point_size=0.01, slippage_points=5.0)

    assert protective_level_fill_quote(1, 100.0, model) == (95.0, 95.6)
    assert protective_level_fill_quote(-1, 100.0, model) == (104.4, 105.0)
    assert bar_stop_fill_quote(1, 100.0, 98.0, 80.0, model) == (93.0, 93.6)
    assert bar_stop_fill_quote(-1, 100.0, 102.0, 80.0, model) == (107.2, 107.8)
```

2. [production caller: `bar_stop_fill_quote`](../../../../trading/execution/quotes.py#L235)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def bar_stop_fill_quote(
    direction: int,
    stop_price: float,
    bar_open: float,
    raw_spread_points: float | None,
    cost_model: CostModel,
) -> tuple[float, float]:
    spread = raw_spread_to_price(raw_spread_points, cost_model.point_size)
    if spread is None:
        spread = float(cost_model.spread_points)
    trigger = bar_stop_trigger_price(direction, stop_price, bar_open, spread)
    return protective_level_fill_quote(direction, trigger, cost_model)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `quote_from_bar_price`

**Kind:** function · **Status:** stable · **Owner:** `trading.execution.quotes`

**Purpose:** Build a quote from a bar price and raw broker spread points.

**Exact API:** {py:obj}`trading.execution.quotes.quote_from_bar_price` · **Source:** [trading/execution/quotes.py:118](../../../../trading/execution/quotes.py#L118)

**Inputs and outputs:**

- **Args:**

  ```text
  cost_model: Cost model used by the operation described above.
  price: Numeric value used for the price.
  spread_points: Spread points used by the operation described above.
  ```

- **Returns:**

  ```text
  Values returned by ``quote_from_bar_price``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_bar_quote_contract_converts_raw_spread_and_uses_default_when_missing`](../../../../tests/integration/backtest/test_engine_execution_contract.py#L79)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_bar_quote_contract_converts_raw_spread_and_uses_default_when_missing() -> None:
    model = CostModel(spread_points=0.6, point_size=0.01)

    assert raw_spread_to_price(80.0, model.point_size) == 0.8
    assert raw_spread_to_price(float("nan"), model.point_size) is None
    assert quote_from_bar_price(model, 100.0, 80.0) == (100.0, 100.8)
    assert quote_from_bar_price(model, 100.0, None) == (100.0, 100.6)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `raw_spread_to_price`

**Kind:** function · **Status:** stable · **Owner:** `trading.execution.quotes`

**Purpose:** Convert a broker-reported spread to price units, preserving missing values.

**Exact API:** {py:obj}`trading.execution.quotes.raw_spread_to_price` · **Source:** [trading/execution/quotes.py:102](../../../../trading/execution/quotes.py#L102)

**Inputs and outputs:**

- **Args:**

  ```text
  raw_spread_points: Raw spread points used by the operation described above.
  point_size: Number specifying the point size for this operation.
  ```

- **Returns:**

  ```text
  Result of convert a broker-reported spread to price units, preserving missing values.
  ```

**Observed usage:**

1. [test fixture: `test_bar_quote_contract_converts_raw_spread_and_uses_default_when_missing`](../../../../tests/integration/backtest/test_engine_execution_contract.py#L77)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_bar_quote_contract_converts_raw_spread_and_uses_default_when_missing() -> None:
    model = CostModel(spread_points=0.6, point_size=0.01)

    assert raw_spread_to_price(80.0, model.point_size) == 0.8
    assert raw_spread_to_price(float("nan"), model.point_size) is None
    assert quote_from_bar_price(model, 100.0, 80.0) == (100.0, 100.8)
    assert quote_from_bar_price(model, 100.0, None) == (100.0, 100.6)
```

2. [production caller: `quote_from_bar_price`](../../../../trading/execution/quotes.py#L131)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def quote_from_bar_price(
    cost_model: CostModel, price: float, spread_points: float | None
) -> tuple[float, float]:
    spread = raw_spread_to_price(spread_points, cost_model.point_size)
    return cost_model.bar_quote(float(price), bar_spread=spread)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `undo_adverse_quote_level_slippage`

**Kind:** function · **Status:** stable · **Owner:** `trading.execution.quotes`

**Purpose:** Undo a modeled protective-level adjustment applied to the whole quote.

**Exact API:** {py:obj}`trading.execution.quotes.undo_adverse_quote_level_slippage` · **Source:** [trading/execution/quotes.py:78](../../../../trading/execution/quotes.py#L78)

**Inputs and outputs:**

- **Args:**

  ```text
  quote: Bid and ask after a whole-quote adjustment.
  direction: Position direction, ``1`` for long or ``-1`` for short.
  slippage_points: Quote shift in instrument points.
  opening: Whether the fill opened the position.
  ```

- **Returns:**

  ```text
  Bid and ask before the modeled quote-level shift.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = undo_adverse_quote_level_slippage(quote=..., direction=..., slippage_points=..., opening=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `undo_adverse_tick_slippage_quote`

**Kind:** function · **Status:** stable · **Owner:** `trading.execution.quotes`

**Purpose:** Recover the executable quote before an already-applied adverse adjustment.

**Exact API:** {py:obj}`trading.execution.quotes.undo_adverse_tick_slippage_quote` · **Source:** [trading/execution/quotes.py:46](../../../../trading/execution/quotes.py#L46)

**Inputs and outputs:**

- **Args:**

  ```text
  quote: Bid and ask after tick-side slippage was applied.
  direction: Position direction, ``1`` for long or ``-1`` for short.
  slippage_points: Adverse adjustment in instrument points.
  opening: Whether the fill opened the position.
  ```

- **Returns:**

  ```text
  Bid and ask before the modeled slippage adjustment.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = undo_adverse_tick_slippage_quote(quote=..., direction=..., slippage_points=..., opening=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
