# Integrations · `mt5.domain.trader`

This page contains 8 public callable records owned by `integrations.mt5.domain.trader`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `MT5Trader`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Execution adapter for submitting and managing MetaTrader positions.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader` · **Source:** [integrations/mt5/domain/trader.py:8](../../../../integrations/mt5/domain/trader.py#L8)

**Observed usage:**

1. [test fixture: `test_close_position_uses_executable_quote_side`](../../../../tests/unit/live/test_mt5_trader_quotes.py#L45)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    monkeypatch: pytest.MonkeyPatch,
    position_type: int,
    expected_order_type: int,
    expected_price: float,
) -> None:
    trader = MT5Trader()
    positions = pd.DataFrame(
        [{"ticket": 17, "symbol": "US100.cash", "volume": 0.2, "type": position_type}]
    )
    submitted: list[dict[str, object]] = []
    monkeypatch.setattr(trader, "get_all_positions", lambda: positions)
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Execution adapter for submitting and managing MetaTrader positions.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader` · **Source:** [integrations/mt5/domain/trader.py:8](../../../../integrations/mt5/domain/trader.py#L8)

**Observed usage:**

1. [test fixture: `test_close_position_uses_executable_quote_side`](../../../../tests/unit/live/test_mt5_trader_quotes.py#L45)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    monkeypatch: pytest.MonkeyPatch,
    position_type: int,
    expected_order_type: int,
    expected_price: float,
) -> None:
    trader = MT5Trader()
    positions = pd.DataFrame(
        [{"ticket": 17, "symbol": "US100.cash", "volume": 0.2, "type": position_type}]
    )
    submitted: list[dict[str, object]] = []
    monkeypatch.setattr(trader, "get_all_positions", lambda: positions)
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader.calculate_position_size`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Calculate lots for a stop distance and risk fraction.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader.calculate_position_size` · **Source:** [integrations/mt5/domain/trader.py:227](../../../../integrations/mt5/domain/trader.py#L227)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Broker symbol whose contract and tick values determine sizing.
  stop_loss: Stop-loss distance in price units.
  per_to_risk: Fraction of account equity to risk.
  ```

- **Returns:**

  ```text
  Position size in broker lots.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MT5Trader(...)
result = instance.calculate_position_size(symbol=..., stop_loss=..., per_to_risk=...)
```

**Lifecycle context:** This callable participates in `MT5Trader`: Execution adapter for submitting and managing MetaTrader positions. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.trader.MT5Trader.open_position`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.close_positions`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.get_opened_positions`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.get_all_positions`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.send_to_break_even`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.calculate_position_size`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader.close_positions`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Close matching open positions owned by the named robot.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader.close_positions` · **Source:** [integrations/mt5/domain/trader.py:64](../../../../integrations/mt5/domain/trader.py#L64)

**Inputs and outputs:**

- **Args:**

  ```text
  robot_name: Strategy identifier used to filter positions.
  symbol: Optional broker symbol filter.
  position_type: Optional MetaTrader position type filter.
  ```

**Observed usage:**

1. [test fixture: `test_close_position_uses_executable_quote_side`](../../../../tests/unit/live/test_mt5_trader_quotes.py#L59)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        lambda _symbol: SimpleNamespace(bid=100.1, ask=100.2),
        raising=False,
    )
    monkeypatch.setattr(mt5, "order_send", lambda order: submitted.append(order), raising=False)

    trader.close_positions("test", symbol="US100.cash", position_type=position_type)

    assert len(submitted) == 1
    assert submitted[0]["type"] == expected_order_type
    assert submitted[0]["price"] == expected_price
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader.get_all_positions`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Fetch all currently open positions as a data frame.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader.get_all_positions` · **Source:** [integrations/mt5/domain/trader.py:163](../../../../integrations/mt5/domain/trader.py#L163)

**Inputs and outputs:**

- **Returns:**

  ```text
  DataFrame returned by ``get_all_positions``.
  ```

**Observed usage:**

1. [production caller: `close_positions`](../../../../integrations/mt5/domain/trader.py#L74)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
        df_open_positions = self.get_all_positions()

        if not df_open_positions.empty:
            if not symbol and position_type is None:
                position_list = df_open_positions["ticket"].unique().tolist()
            elif symbol and position_type is None:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader.get_opened_positions`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Return matching open positions and their total volume.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader.get_opened_positions` · **Source:** [integrations/mt5/domain/trader.py:129](../../../../integrations/mt5/domain/trader.py#L129)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Optional broker symbol filter.
  position_type: Optional MetaTrader position type filter.
  ```

- **Returns:**

  ```text
  Pair containing total volume and the filtered position frame.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MT5Trader(...)
result = instance.get_opened_positions(symbol=..., position_type=...)
```

**Lifecycle context:** This callable participates in `MT5Trader`: Execution adapter for submitting and managing MetaTrader positions. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.trader.MT5Trader.open_position`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.close_positions`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.get_opened_positions`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.get_all_positions`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.send_to_break_even`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.calculate_position_size`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader.open_position`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Submit a market order and optionally attach stop and target prices.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader.open_position` · **Source:** [integrations/mt5/domain/trader.py:11](../../../../integrations/mt5/domain/trader.py#L11)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Broker symbol to trade.
  volume: Requested position size in lots.
  position_type: MetaTrader buy or sell order code.
  comment: Broker-visible order comment.
  magic_number: Strategy identifier stored with the order.
  sl: Optional stop-loss price.
  tp: Optional take-profit price.
  ```

- **Returns:**

  ```text
  Result of submit a market order and optionally attach stop and target prices.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MT5Trader(...)
result = instance.open_position(symbol=..., volume=..., position_type=..., comment=..., magic_number=..., sl=..., tp=...)
```

**Lifecycle context:** This callable participates in `MT5Trader`: Execution adapter for submitting and managing MetaTrader positions. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.trader.MT5Trader.open_position`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.close_positions`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.get_opened_positions`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.get_all_positions`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.send_to_break_even`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.calculate_position_size`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader.send_to_break_even`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Move eligible positions' stop losses to their break-even price.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader.send_to_break_even` · **Source:** [integrations/mt5/domain/trader.py:178](../../../../integrations/mt5/domain/trader.py#L178)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Positions selected for adjustment.
  percentage: Profit threshold used to trigger the adjustment.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MT5Trader(...)
result = instance.send_to_break_even(df=..., percentage=...)
```

**Lifecycle context:** This callable participates in `MT5Trader`: Execution adapter for submitting and managing MetaTrader positions. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.trader.MT5Trader.open_position`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.close_positions`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.get_opened_positions`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.get_all_positions`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.send_to_break_even`, {py:obj}`integrations.mt5.domain.trader.MT5Trader.calculate_position_size`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
