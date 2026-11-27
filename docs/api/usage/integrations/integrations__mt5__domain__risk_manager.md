# Integrations · `mt5.domain.risk_manager`

This page contains 10 public callable records owned by `integrations.mt5.domain.risk_manager`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `RiskManager`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Manage risk across multiple trading positions.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager` · **Source:** [integrations/mt5/domain/risk_manager.py:11](../../../../integrations/mt5/domain/risk_manager.py#L11)

**Observed usage:**

1. [test fixture: `test_missing_current_quote_blocks_sizing_without_mutating_orders_or_account`](../../../../tests/unit/integrations/test_mt5_multi_symbol_risk_contracts.py#L168)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    monkeypatch.setattr(mt5, "symbol_info_tick", stale_tick, raising=False)
    monkeypatch.setattr(
        mt5, "account_info", lambda: pytest.fail("quote check precedes sizing"), raising=False
    )

    robot, trader, _ = _robot(signal=Signal.BUY, risk=cast(Any, RiskManager()))
    robot.trade_symbol("US100")

    assert calls == [("select", ("US100", True)), ("info", "US100"), ("tick", "US100")]
    assert trader.queries == [mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_BUY]
    assert trader.writes == []
# … caller assertions omitted …
```

2. [test fixture: `test_exposure_accepts_mapping_records_and_reports_empty_account`](../../../../tests/unit/integrations/test_mt5_multi_symbol_risk_contracts.py#L206)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
) -> None:
    info = SimpleNamespace(trade_tick_size=0.01, trade_tick_value=1.0)
    monkeypatch.setattr(mt5, "positions_get", lambda: positions, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: info, raising=False)

    exposure = RiskManager().get_total_exposure()

    assert exposure["total_positions"] == len(positions)
    assert exposure["total_open_risk"] == pytest.approx(expected_risk)
    assert exposure["total_open_execution_reserve"] == pytest.approx(expected_reserve)
    assert exposure["risk_unknown_positions"] == 0
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Manage risk across multiple trading positions.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager` · **Source:** [integrations/mt5/domain/risk_manager.py:11](../../../../integrations/mt5/domain/risk_manager.py#L11)

**Observed usage:**

1. [test fixture: `test_missing_current_quote_blocks_sizing_without_mutating_orders_or_account`](../../../../tests/unit/integrations/test_mt5_multi_symbol_risk_contracts.py#L168)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    monkeypatch.setattr(mt5, "symbol_info_tick", stale_tick, raising=False)
    monkeypatch.setattr(
        mt5, "account_info", lambda: pytest.fail("quote check precedes sizing"), raising=False
    )

    robot, trader, _ = _robot(signal=Signal.BUY, risk=cast(Any, RiskManager()))
    robot.trade_symbol("US100")

    assert calls == [("select", ("US100", True)), ("info", "US100"), ("tick", "US100")]
    assert trader.queries == [mt5.ORDER_TYPE_SELL, mt5.ORDER_TYPE_BUY]
    assert trader.writes == []
# … caller assertions omitted …
```

2. [test fixture: `test_exposure_accepts_mapping_records_and_reports_empty_account`](../../../../tests/unit/integrations/test_mt5_multi_symbol_risk_contracts.py#L206)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
) -> None:
    info = SimpleNamespace(trade_tick_size=0.01, trade_tick_value=1.0)
    monkeypatch.setattr(mt5, "positions_get", lambda: positions, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: info, raising=False)

    exposure = RiskManager().get_total_exposure()

    assert exposure["total_positions"] == len(positions)
    assert exposure["total_open_risk"] == pytest.approx(expected_risk)
    assert exposure["total_open_execution_reserve"] == pytest.approx(expected_reserve)
    assert exposure["risk_unknown_positions"] == 0
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.calculate_position_size`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Calculate position size based on stop loss and risk amount.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_position_size` · **Source:** [integrations/mt5/domain/risk_manager.py:268](../../../../integrations/mt5/domain/risk_manager.py#L268)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Trading symbol
  stop_loss_pips: Stop loss in pips (or points for non-forex)
  risk_amount: Amount to risk (if None, uses risk_per_symbol * balance)
  volatility_multiplier: Multiplier to adjust for volatility; higher values reduce size.
  ```

- **Returns:**

  ```text
  Position size in lots
  ```

**Observed usage:**

1. [test fixture: `test_sizing_stops_when_symbol_selection_fails`](../../../../tests/unit/integrations/test_mt5_risk_manager_edges.py#L49)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_sizing_stops_when_symbol_selection_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: False, raising=False)
    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda symbol: calls.append(symbol),
        raising=False,
    )

    size = RiskManager().calculate_position_size("US100", stop_loss_pips=10.0)

    assert size == 0.0
    assert calls == []
```

2. [test fixture: `test_sizing_rejects_missing_symbol_or_invalid_volume_metadata`](../../../../tests/unit/integrations/test_mt5_risk_manager_edges.py#L224)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "symbol_info_tick",
        lambda _symbol: SimpleNamespace(bid=99.9, ask=100.1),
        raising=False,
    )

    size = RiskManager().calculate_position_size("US100", stop_loss_pips=10.0, risk_amount=100.0)

    assert size == 0.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.calculate_stop_loss_price`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Build the broker-side SL using the same distance used for sizing.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_stop_loss_price` · **Source:** [integrations/mt5/domain/risk_manager.py:397](../../../../integrations/mt5/domain/risk_manager.py#L397)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Text or path value identifying the symbol.
  position_type: Numeric value used for the position type.
  stop_loss_pips: Numeric value used for the stop loss pips.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``calculate_stop_loss_price``.
  ```

**Observed usage:**

1. [test fixture: `test_stop_price_requires_valid_tick_metadata_and_quote`](../../../../tests/unit/integrations/test_mt5_risk_manager_edges.py#L88)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    manager = RiskManager()

    info.trade_tick_size = 0.0
    with pytest.raises(ValueError, match="invalid symbol tick data"):
        manager.calculate_stop_loss_price("US100", 0, 10.0)

    info.trade_tick_size = 0.01
    monkeypatch.setattr(mt5, "symbol_info_tick", lambda _symbol: None, raising=False)
    with pytest.raises(ValueError, match="Missing symbol or quote data"):
        manager.calculate_stop_loss_price("US100", 0, 10.0)
```

2. [test fixture: `test_stop_price_uses_directional_quote_and_precision`](../../../../tests/unit/integrations/test_mt5_risk_manager_edges.py#L335)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_stop_price_uses_directional_quote_and_precision(
    monkeypatch: pytest.MonkeyPatch, position_type: int, tick: object, expected: float
) -> None:
    monkeypatch.setattr(mt5, "symbol_select", lambda *_args: True, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: _symbol_info(), raising=False)
    monkeypatch.setattr(mt5, "symbol_info_tick", lambda _symbol: tick, raising=False)

    price = RiskManager().calculate_stop_loss_price("US100", position_type, 10.0)

    assert price == pytest.approx(expected)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.check_risk_limits`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Check if proposed position would exceed risk limits.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.check_risk_limits` · **Source:** [integrations/mt5/domain/risk_manager.py:549](../../../../integrations/mt5/domain/risk_manager.py#L549)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Trading symbol
  proposed_position_size: Proposed position size in lots
  stop_loss_pips: Stop loss in pips
  ```

- **Returns:**

  ```text
  Tuple of (is_allowed, reason_message)
  ```

**Observed usage:**

1. [test fixture: `test_missing_symbol_metadata_marks_open_execution_reserve_unknown`](../../../../tests/unit/integrations/test_mt5_risk_manager_edges.py#L119)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        mt5, "account_info", lambda: SimpleNamespace(balance=100_000.0), raising=False
    )

    manager = RiskManager()
    exposure = manager.get_total_exposure()
    allowed, reason = manager.check_risk_limits("US100", 1.0, 10.0)

    assert exposure["risk_unknown_positions"] == 1
    assert exposure["total_open_execution_reserve"] == 0.0
    assert allowed is False
    assert "risk is unknown" in reason
```

2. [test fixture: `test_sizing_and_risk_check_reject_invalid_config_and_proposals`](../../../../tests/unit/integrations/test_mt5_risk_manager_edges.py#L309)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert manager.calculate_position_size("US100", stop_loss_pips=10.0) == 0.0

    monkeypatch.setattr(
        mt5, "account_info", lambda: SimpleNamespace(balance=100_000.0), raising=False
    )
    allowed, reason = manager.check_risk_limits(
        "US100", proposed_position_size=0.0, stop_loss_pips=10.0
    )
    assert not allowed
    assert "nonpositive" in reason
    allowed, reason = RiskManager(risk_per_symbol=0.0).check_risk_limits(
        "US100", proposed_position_size=1.0, stop_loss_pips=10.0
    )
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.get_account_balance`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Get current account balance.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_balance` · **Source:** [integrations/mt5/domain/risk_manager.py:130](../../../../integrations/mt5/domain/risk_manager.py#L130)

**Inputs and outputs:**

- **Returns:**

  ```text
  Account balance in account currency
  ```

**Observed usage:**

1. [test fixture: `test_account_balance_is_unavailable_when_terminal_has_no_account`](../../../../tests/unit/integrations/test_mt5_risk_manager_edges.py#L60)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_account_balance_is_unavailable_when_terminal_has_no_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mt5, "account_info", lambda: None, raising=False)

    assert RiskManager().get_account_balance() == 0.0
```

2. [test fixture: `test_account_balance_returns_zero_when_terminal_query_raises`](../../../../tests/unit/integrations/test_mt5_risk_manager_edges.py#L271)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_account_balance_returns_zero_when_terminal_query_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_query() -> None:
        raise RuntimeError("terminal disconnected")

    monkeypatch.setattr(mt5, "account_info", fail_query, raising=False)

    assert RiskManager().get_account_balance() == 0.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.get_account_equity`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Get current account equity (balance + floating P/L).

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_equity` · **Source:** [integrations/mt5/domain/risk_manager.py:150](../../../../integrations/mt5/domain/risk_manager.py#L150)

**Inputs and outputs:**

- **Returns:**

  ```text
  Account equity in account currency
  ```

**Observed usage:**

1. [test fixture: `test_account_equity_is_zero_when_terminal_value_is_missing_or_invalid`](../../../../tests/unit/integrations/test_mt5_risk_manager_edges.py#L72)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_account_equity_is_zero_when_terminal_value_is_missing_or_invalid(
    monkeypatch: pytest.MonkeyPatch, account: object | None
) -> None:
    monkeypatch.setattr(mt5, "account_info", lambda: account, raising=False)

    assert RiskManager().get_account_equity() == 0.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.get_total_exposure`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Get stop risk and modeled execution reserve across open positions.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_total_exposure` · **Source:** [integrations/mt5/domain/risk_manager.py:438](../../../../integrations/mt5/domain/risk_manager.py#L438)

**Inputs and outputs:**

- **Args:**

  ```text
  symbols: Optional list of symbols to filter by
  ```

- **Returns:**

  ```text
  Exposure metrics keep broker-stop risk separate from execution reserve.
  ```

**Observed usage:**

1. [test fixture: `test_exposure_accepts_mapping_records_and_reports_empty_account`](../../../../tests/unit/integrations/test_mt5_multi_symbol_risk_contracts.py#L206)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
) -> None:
    info = SimpleNamespace(trade_tick_size=0.01, trade_tick_value=1.0)
    monkeypatch.setattr(mt5, "positions_get", lambda: positions, raising=False)
    monkeypatch.setattr(mt5, "symbol_info", lambda _symbol: info, raising=False)

    exposure = RiskManager().get_total_exposure()

    assert exposure["total_positions"] == len(positions)
    assert exposure["total_open_risk"] == pytest.approx(expected_risk)
    assert exposure["total_open_execution_reserve"] == pytest.approx(expected_reserve)
    assert exposure["risk_unknown_positions"] == 0
# … caller assertions omitted …
```

2. [test fixture: `test_missing_symbol_metadata_marks_open_execution_reserve_unknown`](../../../../tests/unit/integrations/test_mt5_risk_manager_edges.py#L118)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    monkeypatch.setattr(
        mt5, "account_info", lambda: SimpleNamespace(balance=100_000.0), raising=False
    )

    manager = RiskManager()
    exposure = manager.get_total_exposure()
    allowed, reason = manager.check_risk_limits("US100", 1.0, 10.0)

    assert exposure["risk_unknown_positions"] == 1
    assert exposure["total_open_execution_reserve"] == 0.0
    assert allowed is False
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.get_volatility_multiplier`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Calculate the volatility multiplier for position sizing.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_volatility_multiplier` · **Source:** [integrations/mt5/domain/risk_manager.py:642](../../../../integrations/mt5/domain/risk_manager.py#L642)

**Inputs and outputs:**

- **Args:**

  ```text
  atr_percentage: ATR as percentage of price
  base_atr: Base ATR percentage for normalization (default: 1.0%)
  ```

- **Returns:**

  ```text
  Multiplier (typically 0.5 to 2.0)
  ```

**Observed usage:**

1. [test fixture: `test_volatility_multiplier_handles_invalid_zero_and_clamped_values`](../../../../tests/unit/integrations/test_mt5_risk_manager_edges.py#L423)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_volatility_multiplier_handles_invalid_zero_and_clamped_values(
    atr: float | str, base: float, expected: float
) -> None:
    assert RiskManager().get_volatility_multiplier(cast(Any, atr), base) == pytest.approx(expected)
```

2. [test fixture: `test_invalid_atr_cannot_increase_or_preserve_position_size`](../../../../tests/unit/live/test_risk_manager.py#L375)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_invalid_atr_cannot_increase_or_preserve_position_size(
    mt5_risk_api: dict[str, Any], atr_percentage: float, base_atr: float
) -> None:
    manager = RiskManager()

    multiplier = manager.get_volatility_multiplier(atr_percentage, base_atr)

    assert multiplier == 0.0
    assert (
        manager.calculate_position_size(
            "US100.cash", stop_loss_pips=50.0, volatility_multiplier=multiplier
        )
        == 0.0
    )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.supports_training_account_loss_guardrails`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Whether this manager enforces the training daily and max-loss limits.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.supports_training_account_loss_guardrails` · **Source:** [integrations/mt5/domain/risk_manager.py:19](../../../../integrations/mt5/domain/risk_manager.py#L19)

**Inputs and outputs:**

- **Returns:**

  ```text
  ``False`` because this manager lacks restart-safe training account state.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = RiskManager(...)
value = instance.supports_training_account_loss_guardrails
```

**Lifecycle context:** This callable participates in `RiskManager`: Manage risk across multiple trading positions. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.supports_training_account_loss_guardrails`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_balance`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_equity`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_position_size`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_stop_loss_price`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_total_exposure`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.check_risk_limits`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_volatility_multiplier`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
