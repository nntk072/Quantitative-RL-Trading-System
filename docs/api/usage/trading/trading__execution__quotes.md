# Trading · `execution.quotes`

This page contains 5 public callable records owned by `trading.execution.quotes`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `bar_stop_fill_quote`

**Kind:** function · **Status:** stable · **Owner:** `trading.execution.quotes`

**Purpose:** Price a bar stop at its level or at a worse opening quote.

**Exact API:** {py:obj}`trading.execution.quotes.bar_stop_fill_quote` · **Source:** [trading/execution/quotes.py:88](../../../../trading/execution/quotes.py#L88)

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

1. [test fixture: `test_trading_quote_contract_owns_protective_and_bar_stop_fills`](../../../../tests/integration/backtest/test_engine_execution_contract.py#L52)

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

**Exact API:** {py:obj}`trading.execution.quotes.bar_stop_trigger_price` · **Source:** [trading/execution/quotes.py:65](../../../../trading/execution/quotes.py#L65)

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

1. [production caller: `bar_stop_fill_quote`](../../../../trading/execution/quotes.py#L110)

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

## `protective_level_fill_quote`

**Kind:** function · **Status:** stable · **Owner:** `trading.execution.quotes`

**Purpose:** Build a bid/ask quote that executes a protective level with adverse slippage.

**Exact API:** {py:obj}`trading.execution.quotes.protective_level_fill_quote` · **Source:** [trading/execution/quotes.py:43](../../../../trading/execution/quotes.py#L43)

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

1. [test fixture: `test_trading_quote_contract_owns_protective_and_bar_stop_fills`](../../../../tests/integration/backtest/test_engine_execution_contract.py#L50)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trading_quote_contract_owns_protective_and_bar_stop_fills() -> None:
    model = CostModel(spread_points=0.6, point_size=0.01, slippage_points=5.0)

    assert protective_level_fill_quote(1, 100.0, model) == (95.0, 95.6)
    assert protective_level_fill_quote(-1, 100.0, model) == (104.4, 105.0)
    assert bar_stop_fill_quote(1, 100.0, 98.0, 80.0, model) == (93.0, 93.6)
    assert bar_stop_fill_quote(-1, 100.0, 102.0, 80.0, model) == (107.2, 107.8)
```

2. [production caller: `bar_stop_fill_quote`](../../../../trading/execution/quotes.py#L111)

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

**Exact API:** {py:obj}`trading.execution.quotes.quote_from_bar_price` · **Source:** [trading/execution/quotes.py:26](../../../../trading/execution/quotes.py#L26)

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

1. [test fixture: `test_bar_quote_contract_converts_raw_spread_and_uses_default_when_missing`](../../../../tests/integration/backtest/test_engine_execution_contract.py#L61)

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

**Exact API:** {py:obj}`trading.execution.quotes.raw_spread_to_price` · **Source:** [trading/execution/quotes.py:10](../../../../trading/execution/quotes.py#L10)

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

1. [test fixture: `test_bar_quote_contract_converts_raw_spread_and_uses_default_when_missing`](../../../../tests/integration/backtest/test_engine_execution_contract.py#L59)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_bar_quote_contract_converts_raw_spread_and_uses_default_when_missing() -> None:
    model = CostModel(spread_points=0.6, point_size=0.01)

    assert raw_spread_to_price(80.0, model.point_size) == 0.8
    assert raw_spread_to_price(float("nan"), model.point_size) is None
    assert quote_from_bar_price(model, 100.0, 80.0) == (100.0, 100.8)
    assert quote_from_bar_price(model, 100.0, None) == (100.0, 100.6)
```

2. [production caller: `quote_from_bar_price`](../../../../trading/execution/quotes.py#L39)

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
