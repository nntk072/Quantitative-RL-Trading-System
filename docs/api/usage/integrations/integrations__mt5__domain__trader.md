# Integrations · `mt5.domain.trader`

This page contains 8 public callable records owned by `integrations.mt5.domain.trader`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `MT5Trader`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Execution adapter for submitting and managing MetaTrader positions.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader` · **Source:** [integrations/mt5/domain/trader.py:13](../../../../integrations/mt5/domain/trader.py#L13)

**Observed usage:**

1. [test fixture: `test_send_to_break_even_modifies_stop_only_after_profit_threshold`](../../../../tests/unit/integrations/test_mt5_trader_management.py#L79)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            }
        ]
    )
    monkeypatch.setattr(mt5, "order_send", lambda order: submitted.append(order), raising=False)

    MT5Trader().send_to_break_even(positions, percentage=0.5)

    assert len(submitted) == 1
    assert submitted[0] == {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": "US100",
# … caller assertions omitted …
```

2. [test fixture: `test_calculate_position_size_converts_stop_distance_to_lots`](../../../../tests/unit/integrations/test_mt5_trader_management.py#L126)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "account_info",
        lambda: SimpleNamespace(balance=10_000.0),
        raising=False,
    )

    lots = MT5Trader().calculate_position_size("US100", stop_loss=98.0, per_to_risk=0.01)

    assert lots == pytest.approx(2.5)
    assert calls == [
        ("select", ("US100", True)),
        ("tick", "US100"),
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Execution adapter for submitting and managing MetaTrader positions.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader` · **Source:** [integrations/mt5/domain/trader.py:13](../../../../integrations/mt5/domain/trader.py#L13)

**Observed usage:**

1. [test fixture: `test_send_to_break_even_modifies_stop_only_after_profit_threshold`](../../../../tests/unit/integrations/test_mt5_trader_management.py#L79)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            }
        ]
    )
    monkeypatch.setattr(mt5, "order_send", lambda order: submitted.append(order), raising=False)

    MT5Trader().send_to_break_even(positions, percentage=0.5)

    assert len(submitted) == 1
    assert submitted[0] == {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": "US100",
# … caller assertions omitted …
```

2. [test fixture: `test_calculate_position_size_converts_stop_distance_to_lots`](../../../../tests/unit/integrations/test_mt5_trader_management.py#L126)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "account_info",
        lambda: SimpleNamespace(balance=10_000.0),
        raising=False,
    )

    lots = MT5Trader().calculate_position_size("US100", stop_loss=98.0, per_to_risk=0.01)

    assert lots == pytest.approx(2.5)
    assert calls == [
        ("select", ("US100", True)),
        ("tick", "US100"),
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader.calculate_position_size`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Calculate lots for a stop distance and risk fraction.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader.calculate_position_size` · **Source:** [integrations/mt5/domain/trader.py:291](../../../../integrations/mt5/domain/trader.py#L291)

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

**Observed usage:**

1. [test fixture: `test_calculate_position_size_converts_stop_distance_to_lots`](../../../../tests/unit/integrations/test_mt5_trader_management.py#L126)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "account_info",
        lambda: SimpleNamespace(balance=10_000.0),
        raising=False,
    )

    lots = MT5Trader().calculate_position_size("US100", stop_loss=98.0, per_to_risk=0.01)

    assert lots == pytest.approx(2.5)
    assert calls == [
        ("select", ("US100", True)),
        ("tick", "US100"),
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader.close_positions`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Close open positions owned by the named robot's magic number.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader.close_positions` · **Source:** [integrations/mt5/domain/trader.py:84](../../../../integrations/mt5/domain/trader.py#L84)

**Inputs and outputs:**

- **Args:**

  ```text
  robot_name: Strategy identifier used to filter positions.
  symbol: Optional broker symbol filter.
  position_type: Optional MetaTrader position type filter.
  magic_number: Broker-stored identifier assigned to this strategy.
  ```

**Observed usage:**

1. [test fixture: `test_close_position_skips_request_when_quote_is_unavailable`](../../../../tests/unit/integrations/test_mt5_trader_management.py#L186)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    monkeypatch.setattr(trader, "get_all_positions", lambda: positions)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: _symbol_info(), raising=False)
    monkeypatch.setattr(mt5, "symbol_info_tick", lambda _symbol: None, raising=False)
    monkeypatch.setattr(mt5, "order_send", lambda request: requests.append(request), raising=False)

    trader.close_positions("test", symbol="US100", magic_number=42)

    assert requests == []
```

2. [test fixture: `test_close_position_skips_request_when_symbol_metadata_is_unusable`](../../../../tests/unit/integrations/test_mt5_trader_management.py#L218)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        lambda _symbol: SimpleNamespace(bid=99.9, ask=100.1),
        raising=False,
    )
    monkeypatch.setattr(mt5, "order_send", lambda request: requests.append(request), raising=False)

    trader.close_positions("test", symbol="US100", magic_number=42)

    assert requests == []
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader.get_all_positions`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Fetch all currently open positions as a data frame.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader.get_all_positions` · **Source:** [integrations/mt5/domain/trader.py:210](../../../../integrations/mt5/domain/trader.py#L210)

**Inputs and outputs:**

- **Returns:**

  ```text
  DataFrame returned by ``get_all_positions``.
  ```

**Observed usage:**

1. [test fixture: `test_get_all_positions_returns_empty_frame_for_missing_or_empty_snapshot`](../../../../tests/unit/integrations/test_mt5_trader_management.py#L257)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_get_all_positions_returns_empty_frame_for_missing_or_empty_snapshot(
    monkeypatch: pytest.MonkeyPatch, broker_positions: object
) -> None:
    monkeypatch.setattr(mt5, "positions_get", lambda: broker_positions, raising=False)

    positions = MT5Trader().get_all_positions()

    assert positions.empty
    assert list(positions.columns) == []
```

2. [test fixture: `test_get_all_positions_returns_empty_frame_when_snapshot_query_raises`](../../../../tests/unit/integrations/test_mt5_trader_management.py#L271)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_get_all_positions_returns_empty_frame_when_snapshot_query_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_query_error() -> None:
        raise RuntimeError("terminal disconnected")

    monkeypatch.setattr(mt5, "positions_get", raise_query_error, raising=False)

    positions = MT5Trader().get_all_positions()

    assert positions.empty
    assert list(positions.columns) == []
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader.get_opened_positions`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Return matching open positions and their total volume.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader.get_opened_positions` · **Source:** [integrations/mt5/domain/trader.py:172](../../../../integrations/mt5/domain/trader.py#L172)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Optional broker symbol filter.
  position_type: Optional MetaTrader position type filter.
  magic_number: Optional strategy ownership filter.
  ```

- **Returns:**

  ```text
  Pair containing total volume and the filtered position frame.
  ```

**Observed usage:**

1. [test fixture: `test_get_opened_positions_filters_by_strategy_magic_number`](../../../../tests/unit/live/test_mt5_trader_quotes.py#L407)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            Position(ticket=18, symbol="US100.cash", type=mt5.ORDER_TYPE_BUY, magic=99),
        ),
        raising=False,
    )

    count, positions = trader.get_opened_positions(
        "US100.cash", mt5.ORDER_TYPE_BUY, magic_number=42
    )

    assert count == 1
    assert positions["ticket"].tolist() == [17]
```

2. [test fixture: `test_get_opened_positions_does_not_turn_broker_failure_into_no_positions`](../../../../tests/unit/live/test_mt5_trader_quotes.py#L423)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_get_opened_positions_does_not_turn_broker_failure_into_no_positions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trader = MT5Trader()
    monkeypatch.setattr(mt5, "positions_get", lambda: None, raising=False)
    monkeypatch.setattr(mt5, "last_error", lambda: (1, "terminal unavailable"), raising=False)

    with pytest.raises(RuntimeError, match="terminal unavailable"):
        trader.get_opened_positions("US100.cash", mt5.ORDER_TYPE_BUY, magic_number=42)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader.open_position`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Submit a market order and optionally attach stop and target prices.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader.open_position` · **Source:** [integrations/mt5/domain/trader.py:16](../../../../integrations/mt5/domain/trader.py#L16)

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

**Observed usage:**

1. [test fixture: `test_open_position_returns_none_when_terminal_disables_autotrading`](../../../../tests/unit/integrations/test_mt5_trader_management.py#L165)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "order_send",
        send_order,
        raising=False,
    )

    result = MT5Trader().open_position("US100", 0.1, mt5.ORDER_TYPE_BUY, "test", 42, 99.0, 102.0)

    assert result is None
    assert len(requests) == 1
    assert requests[0]["sl"] == 99.0
    assert requests[0]["tp"] == 102.0
```

2. [test fixture: `test_open_position_uses_a_fill_mode_supported_by_symbol`](../../../../tests/unit/live/test_mt5_trader_quotes.py#L164)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "order_send",
        send_order,
        raising=False,
    )

    result = MT5Trader().open_position("US100.cash", 0.1, 0, "test", 42)

    assert result is not None
    assert submitted[0]["type_filling"] == expected
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `MT5Trader.send_to_break_even`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.trader`

**Purpose:** Move eligible positions' stop losses to their break-even price.

**Exact API:** {py:obj}`integrations.mt5.domain.trader.MT5Trader.send_to_break_even` · **Source:** [integrations/mt5/domain/trader.py:225](../../../../integrations/mt5/domain/trader.py#L225)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Positions selected for adjustment.
  percentage: Profit threshold used to trigger the adjustment.
  ```

**Observed usage:**

1. [test fixture: `test_send_to_break_even_modifies_stop_only_after_profit_threshold`](../../../../tests/unit/integrations/test_mt5_trader_management.py#L79)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            }
        ]
    )
    monkeypatch.setattr(mt5, "order_send", lambda order: submitted.append(order), raising=False)

    MT5Trader().send_to_break_even(positions, percentage=0.5)

    assert len(submitted) == 1
    assert submitted[0] == {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": "US100",
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
