# Trading · `execution.costs`

This page contains 4 public callable records owned by `trading.execution.costs`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `CostModel`

**Kind:** class · **Status:** stable · **Owner:** `trading.execution.costs`

**Purpose:** Holds cost parameters and computes fill costs.

**Exact API:** {py:obj}`trading.execution.costs.CostModel` · **Source:** [trading/execution/costs.py:12](../../../../trading/execution/costs.py#L12)

**Observed usage:**

1. [test fixture: `setUp`](../../../../tests/integration/backtest/test_broker_fill_accounting.py#L14)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def setUp(self):
    self.acc = AccountState(initial_balance=100_000.0)
    self.broker = Broker(cost_model=CostModel(commission_per_lot=2.0))
```

2. [test fixture: `test_mirrored_long_short_round_trip_and_mark_to_market`](../../../../tests/integration/backtest/test_broker_quote_parity.py#L16)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def test_mirrored_long_short_round_trip_and_mark_to_market(self):
        quote = (99.5, 100.5)
        for direction in (1, -1):
            with self.subTest(direction=direction):
                account = AccountState(initial_balance=100_000.0)
                broker = Broker(cost_model=CostModel(commission_per_lot=2.0))
                position = broker.open_position(account, quote, 1.0, direction)
                self.assertIsNotNone(position)
                assert position is not None
                self.assertEqual(position.entry_price, 100.5 if direction == 1 else 99.5)
                self.assertAlmostEqual(account.balance, 99_998.0)
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `CostModel.bar_quote`

**Kind:** method · **Status:** stable · **Owner:** `trading.execution.costs`

**Purpose:** Derive bid/ask from close price using spread.

**Exact API:** {py:obj}`trading.execution.costs.CostModel.bar_quote` · **Source:** [trading/execution/costs.py:56](../../../../trading/execution/costs.py#L56)

**Inputs and outputs:**

- **Args:**

  ```text
  close (float): Bar close price (MT5 close = bid)
  bar_spread (float | None): Spread in points from data, or use default
  ```

- **Returns:**

  ```text
  tuple[float, float]: (bid, ask) prices
  ```

**Observed usage:**

1. [test fixture: `test_bar_quote_derives_ask_from_close`](../../../../tests/unit/trading/test_cost_model.py#L37)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_bar_quote_derives_ask_from_close():
    c = CostModel(spread_points=0.6, point_size=0.01)
    bid, ask = c.bar_quote(close=20000.0)
    assert bid == pytest.approx(20000.0)
    assert ask == pytest.approx(20000.6)
```

2. [production caller: `quote_from_bar_price`](../../../../trading/execution/quotes.py#L132)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def quote_from_bar_price(
    cost_model: CostModel, price: float, spread_points: float | None
) -> tuple[float, float]:
    spread = raw_spread_to_price(spread_points, cost_model.point_size)
    return cost_model.bar_quote(float(price), bar_spread=spread)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `CostModel.fill_price`

**Kind:** method · **Status:** stable · **Owner:** `trading.execution.costs`

**Purpose:** Return the fill price for a market order.

**Exact API:** {py:obj}`trading.execution.costs.CostModel.fill_price` · **Source:** [trading/execution/costs.py:36](../../../../trading/execution/costs.py#L36)

**Inputs and outputs:**

- **Args:**

  ```text
  bid (float): Bid price
  ask (float): Ask price
  direction (int): +1 for long (buy at ask), -1 for short (sell at bid)
  ```

- **Returns:**

  ```text
  Numeric result returned by ``fill_price``.
  ```

**Observed usage:**

1. [test fixture: `test_fill_price_buy_is_ask`](../../../../tests/unit/trading/test_cost_model.py#L20)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fill_price_buy_is_ask():
    c = CostModel(spread_points=1.0, slippage_points=0.0)
    fill = c.fill_price(bid=99.5, ask=100.5, direction=1)
    assert fill == pytest.approx(100.5)
```

2. [test fixture: `test_fill_price_sell_is_bid`](../../../../tests/unit/trading/test_cost_model.py#L26)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fill_price_sell_is_bid():
    c = CostModel(spread_points=1.0, slippage_points=0.0)
    fill = c.fill_price(bid=99.5, ask=100.5, direction=-1)
    assert fill == pytest.approx(99.5)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `CostModel.total_cost`

**Kind:** method · **Status:** stable · **Owner:** `trading.execution.costs`

**Purpose:** Return the explicit transaction cost for one side of a trade.

**Exact API:** {py:obj}`trading.execution.costs.CostModel.total_cost` · **Source:** [trading/execution/costs.py:21](../../../../trading/execution/costs.py#L21)

**Inputs and outputs:**

- **Args:**

  ```text
  lots: Positive trade size in lots.
  direction: +1 = long, -1 = short (unused here but provided for extensibility).
  ```

- **Returns:**

  ```text
  Numeric result returned by ``total_cost``.
  ```

**Observed usage:**

1. [test fixture: `test_total_cost_is_commission_only`](../../../../tests/unit/trading/test_cost_model.py#L32)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_total_cost_is_commission_only():
    c = CostModel(spread_points=0.6, commission_per_lot=3.0)
    assert c.total_cost(lots=2.0) == pytest.approx(6.0)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
