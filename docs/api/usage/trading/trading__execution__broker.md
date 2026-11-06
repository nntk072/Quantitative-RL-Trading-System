# Trading · `execution.broker`

This page contains 6 public callable records owned by `trading.execution.broker`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `Broker`

**Kind:** class · **Status:** stable · **Owner:** `trading.execution.broker`

**Purpose:** Simple broker model used by the simulation execution layer.

**Exact API:** {py:obj}`trading.execution.broker.Broker` · **Source:** [trading/execution/broker.py:129](../../../../trading/execution/broker.py#L129)

**Inputs and outputs:**

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

## `Position`

**Kind:** class · **Status:** stable · **Owner:** `trading.execution.broker`

**Purpose:** Open position state tracked by the broker adapter.

**Exact API:** {py:obj}`trading.execution.broker.Position` · **Source:** [trading/execution/broker.py:46](../../../../trading/execution/broker.py#L46)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `test_stop_wins_when_the_same_bar_crosses_ema`](../../../../tests/integration/backtest/test_entry_levels.py#L781)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        },
        index=idx,
    )
    feats = pd.DataFrame({"ema_21": np.full(n, 101.0)}, index=idx)
    env = TradingEnv(bars, feats, strategy_actions=True, obs_window=5)
    env.position = Position(
        direction=1,
        size=1.0,
        entry_price=100.0,
        margin_used=0.0,
        sl_price=99.0,
        tp_price=None,
        sl_initial_price=99.0,
        exit_mode="ema_21",
        stop_distance=1.0,
        sl_ref="last_swing_low",
        tp_ref="ema_21",
    )
    env.step_idx = 5
    env._check_sl_tp(BarView(100.0, 102.0, 98.5, 99.5), 100.0, 100.0, bar_idx=5)
    assert env.position is None
    assert env.trade_log[-1]["reason"] == "structure_sl"
    assert env.trade_log[-1]["price"] == pytest.approx(99.0)
```

2. [test fixture: `test_partial_fills_accumulate_once_and_complete_only_at_final_fill`](../../../../tests/integration/test_position_fill_accounting.py#L14)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_partial_fills_accumulate_once_and_complete_only_at_final_fill() -> None:
    pos = Position(
        direction=1,
        size=0.7,
        entry_price=100.0,
        margin_used=0.0,
        sl_ref="swing_low",
        tp_ref="target",
        stop_distance=5.0,
        planned_risk_usd=50.0,
        tp_initial_size=1.0,
    )
    pos.position_id = "e1:p1"
    pos.initial_size = 1.0
    env: Any = SimpleNamespace(
        position=pos,
        trade_log=[{"type": "open", "position_id": "e1:p1"}],
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `Broker.close_position`

**Kind:** method · **Status:** stable · **Owner:** `trading.execution.broker`

**Purpose:** Close an open position (or part of it) and return (pnl, fill_price).

**Exact API:** {py:obj}`trading.execution.broker.Broker.close_position` · **Source:** [trading/execution/broker.py:202](../../../../trading/execution/broker.py#L202)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Acc used by the operation described above.
  position: Position used by the operation described above.
  quote: Quote used by the operation described above.
  size: Size used by the operation described above.
  ```

- **Returns:**

  ```text
  tuple of (realised_pnl, fill_price)
  ```

**Observed usage:**

1. [test fixture: `test_mirrored_long_short_round_trip_and_mark_to_market`](../../../../tests/integration/backtest/test_broker_quote_parity.py#L25)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                self.assertEqual(position.entry_price, 100.5 if direction == 1 else 99.5)
                self.assertAlmostEqual(account.balance, 99_998.0)
                self.assertAlmostEqual(broker.mark_to_market(account, position, quote), -1.0)
                self.assertAlmostEqual(account.equity, 99_997.0)

                pnl1, fill1 = broker.close_position(account, position, quote, 0.4)
                pnl2, fill2 = broker.close_position(account, position, quote)
                expected_exit = 99.5 if direction == 1 else 100.5
                self.assertEqual((fill1, fill2), (expected_exit, expected_exit))
                self.assertAlmostEqual(pnl1, -1.2)
                self.assertAlmostEqual(pnl2, -1.8)
# … caller assertions omitted …
```

2. [test fixture: `test_tick_quote_sides_match_buy_ask_and_sell_bid_for_entries_and_exits`](../../../../tests/unit/simulation/test_environment/test_tick_fill_reconciliation.py#L90)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    long_account = AccountState(initial_balance=100_000.0)
    long_position = broker.open_position(long_account, quote, 1.0, 1)
    assert long_position is not None
    assert long_position.entry_price == pytest.approx(101.0)  # Buy at ask.
    _, long_exit = broker.close_position(long_account, long_position, quote)
    assert long_exit == pytest.approx(99.0)  # Sell at bid.

    short_account = AccountState(initial_balance=100_000.0)
    short_position = broker.open_position(short_account, quote, 1.0, -1)
    assert short_position is not None
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `Broker.mark_to_market`

**Kind:** method · **Status:** stable · **Owner:** `trading.execution.broker`

**Purpose:** Recompute and record unrealised P&L using the close-side price.

**Exact API:** {py:obj}`trading.execution.broker.Broker.mark_to_market` · **Source:** [trading/execution/broker.py:245](../../../../trading/execution/broker.py#L245)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Acc used by the operation described above.
  position: Position used by the operation described above.
  quote: Quote used by the operation described above.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``mark_to_market``.
  ```

**Observed usage:**

1. [test fixture: `test_mirrored_long_short_round_trip_and_mark_to_market`](../../../../tests/integration/backtest/test_broker_quote_parity.py#L22)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                position = broker.open_position(account, quote, 1.0, direction)
                self.assertIsNotNone(position)
                assert position is not None
                self.assertEqual(position.entry_price, 100.5 if direction == 1 else 99.5)
                self.assertAlmostEqual(account.balance, 99_998.0)
                self.assertAlmostEqual(broker.mark_to_market(account, position, quote), -1.0)
                self.assertAlmostEqual(account.equity, 99_997.0)

                pnl1, fill1 = broker.close_position(account, position, quote, 0.4)
                pnl2, fill2 = broker.close_position(account, position, quote)
                expected_exit = 99.5 if direction == 1 else 100.5
# … caller assertions omitted …
```

2. [production caller: `close_position`](../../../../trading/execution/broker.py#L242)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        if position.size <= 1e-9:
            position.size = 0.0
            position.margin_used = 0.0
        else:
            position.margin_used = self.required_margin(position.entry_price, position.size)
            self.mark_to_market(acc, position, quote)
        return pnl, fill
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `Broker.open_position`

**Kind:** method · **Status:** stable · **Owner:** `trading.execution.broker`

**Purpose:** Attempt to open a position.

**Exact API:** {py:obj}`trading.execution.broker.Broker.open_position` · **Source:** [trading/execution/broker.py:159](../../../../trading/execution/broker.py#L159)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Acc used by the operation described above.
  quote: Quote used by the operation described above.
  lots: Numeric value used for the lots.
  direction: Signed trade direction: 1 for long and -1 for short.
  ```

- **Returns:**

  ```text
  Result of attempt to open a position.
  ```

**Observed usage:**

1. [test fixture: `test_mirrored_long_short_round_trip_and_mark_to_market`](../../../../tests/integration/backtest/test_broker_quote_parity.py#L17)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
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
                self.assertAlmostEqual(broker.mark_to_market(account, position, quote), -1.0)
# … caller assertions omitted …
```

2. [test fixture: `test_tick_quote_sides_match_buy_ask_and_sell_bid_for_entries_and_exits`](../../../../tests/unit/simulation/test_environment/test_tick_fill_reconciliation.py#L87)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_tick_quote_sides_match_buy_ask_and_sell_bid_for_entries_and_exits() -> None:
    quote = (99.0, 101.0)
    broker = Broker(cost_model=CostModel(spread_points=0.0, commission_per_lot=0.0))

    long_account = AccountState(initial_balance=100_000.0)
    long_position = broker.open_position(long_account, quote, 1.0, 1)
    assert long_position is not None
    assert long_position.entry_price == pytest.approx(101.0)  # Buy at ask.
    _, long_exit = broker.close_position(long_account, long_position, quote)
    assert long_exit == pytest.approx(99.0)  # Sell at bid.

# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `Broker.required_margin`

**Kind:** method · **Status:** stable · **Owner:** `trading.execution.broker`

**Purpose:** Calculate margin required to open the requested position.

**Exact API:** {py:obj}`trading.execution.broker.Broker.required_margin` · **Source:** [trading/execution/broker.py:147](../../../../trading/execution/broker.py#L147)

**Inputs and outputs:**

- **Args:**

  ```text
  price: Current instrument price.
  lots: Absolute number of lots requested.
  ```

- **Returns:**

  ```text
  Required margin in account currency.
  ```

**Observed usage:**

1. [production caller: `open_position`](../../../../trading/execution/broker.py#L188)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            # must never reach open_position. Reject rather than open a
            # bogus position with an undefined side.
            return None
        bid, ask = _validate_quote(quote)
        fill = self.cost_model.fill_price(bid, ask, direction)
        margin = self.required_margin(fill, lots)
        if acc.equity < margin:
            return None
        cost = self.cost_model.total_cost(lots)
        acc.balance -= cost
        return Position(
# … caller assertions omitted …
```

2. [production caller: `close_position`](../../../../trading/execution/broker.py#L241)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        position.size -= close_size
        if position.size <= 1e-9:
            position.size = 0.0
            position.margin_used = 0.0
        else:
            position.margin_used = self.required_margin(position.entry_price, position.size)
            self.mark_to_market(acc, position, quote)
        return pnl, fill
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
