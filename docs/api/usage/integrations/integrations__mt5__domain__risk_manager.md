# Integrations · `mt5.domain.risk_manager`

This page contains 10 public callable records owned by `integrations.mt5.domain.risk_manager`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `RiskManager`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Manage risk across multiple trading positions.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager` · **Source:** [integrations/mt5/domain/risk_manager.py:10](../../../../integrations/mt5/domain/risk_manager.py#L10)

**Observed usage:**

1. [test fixture: `test_multi_symbol_robot_rejects_real_order_mode_without_account_loss_guardrails`](../../../../tests/unit/live/test_multi_symbol_risk_stops.py#L149)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_multi_symbol_robot_rejects_real_order_mode_without_account_loss_guardrails() -> None:
    trader = _Trader()
    symbol = "US100.cash"
    with pytest.raises(ValueError, match="training-equivalent daily and maximum account-loss"):
        MultiSymbolRobot(
            symbol_manager=cast(Any, _Symbols()),
            trader=trader,  # type: ignore[arg-type]
            strategies=cast(Any, {symbol: _Strategy(symbol, Signal.BUY)}),
            risk_manager=RiskManager(),
            paper_trading=False,
        )
```

2. [test fixture: `test_sizing_rounds_down_and_stop_price_uses_same_distance`](../../../../tests/unit/live/test_risk_manager.py#L58)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_sizing_rounds_down_and_stop_price_uses_same_distance(
    mt5_risk_api: dict[str, Any],
) -> None:
    manager = RiskManager(risk_per_symbol=0.01, max_total_risk=0.02)

    size = manager.calculate_position_size("US100.cash", stop_loss_pips=50.0)
    buy_stop = manager.calculate_stop_loss_price("US100.cash", mt5.ORDER_TYPE_BUY, 50.0)
    sell_stop = manager.calculate_stop_loss_price("US100.cash", mt5.ORDER_TYPE_SELL, 50.0)

# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Manage risk across multiple trading positions.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager` · **Source:** [integrations/mt5/domain/risk_manager.py:10](../../../../integrations/mt5/domain/risk_manager.py#L10)

**Observed usage:**

1. [test fixture: `test_multi_symbol_robot_rejects_real_order_mode_without_account_loss_guardrails`](../../../../tests/unit/live/test_multi_symbol_risk_stops.py#L149)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_multi_symbol_robot_rejects_real_order_mode_without_account_loss_guardrails() -> None:
    trader = _Trader()
    symbol = "US100.cash"
    with pytest.raises(ValueError, match="training-equivalent daily and maximum account-loss"):
        MultiSymbolRobot(
            symbol_manager=cast(Any, _Symbols()),
            trader=trader,  # type: ignore[arg-type]
            strategies=cast(Any, {symbol: _Strategy(symbol, Signal.BUY)}),
            risk_manager=RiskManager(),
            paper_trading=False,
        )
```

2. [test fixture: `test_sizing_rounds_down_and_stop_price_uses_same_distance`](../../../../tests/unit/live/test_risk_manager.py#L58)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_sizing_rounds_down_and_stop_price_uses_same_distance(
    mt5_risk_api: dict[str, Any],
) -> None:
    manager = RiskManager(risk_per_symbol=0.01, max_total_risk=0.02)

    size = manager.calculate_position_size("US100.cash", stop_loss_pips=50.0)
    buy_stop = manager.calculate_stop_loss_price("US100.cash", mt5.ORDER_TYPE_BUY, 50.0)
    sell_stop = manager.calculate_stop_loss_price("US100.cash", mt5.ORDER_TYPE_SELL, 50.0)

# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.calculate_position_size`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Calculate position size based on stop loss and risk amount.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_position_size` · **Source:** [integrations/mt5/domain/risk_manager.py:267](../../../../integrations/mt5/domain/risk_manager.py#L267)

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

1. [test fixture: `test_sizing_rounds_down_and_stop_price_uses_same_distance`](../../../../tests/unit/live/test_risk_manager.py#L60)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_sizing_rounds_down_and_stop_price_uses_same_distance(
    mt5_risk_api: dict[str, Any],
) -> None:
    manager = RiskManager(risk_per_symbol=0.01, max_total_risk=0.02)

    size = manager.calculate_position_size("US100.cash", stop_loss_pips=50.0)
    buy_stop = manager.calculate_stop_loss_price("US100.cash", mt5.ORDER_TYPE_BUY, 50.0)
    sell_stop = manager.calculate_stop_loss_price("US100.cash", mt5.ORDER_TYPE_SELL, 50.0)

    assert size == pytest.approx(20.0)
    assert buy_stop == pytest.approx(99.51)
# … caller assertions omitted …
```

2. [test fixture: `test_absolute_per_symbol_cap_limits_sizing_and_risk_acceptance`](../../../../tests/unit/live/test_risk_manager.py#L91)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        risk_per_symbol=0.01,
        max_total_risk=0.02,
        risk_per_symbol_usd_cap=900.0,
    )

    size = manager.calculate_position_size("US100.cash", stop_loss_pips=50.0)
    allowed, message = manager.check_risk_limits("US100.cash", 18.01, 50.0)

    assert size == pytest.approx(18.0)
    assert allowed is False
    assert "per-symbol limit ($900.00" in message
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.calculate_stop_loss_price`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Build the broker-side SL using the same distance used for sizing.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_stop_loss_price` · **Source:** [integrations/mt5/domain/risk_manager.py:394](../../../../integrations/mt5/domain/risk_manager.py#L394)

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

1. [test fixture: `test_sizing_rounds_down_and_stop_price_uses_same_distance`](../../../../tests/unit/live/test_risk_manager.py#L61)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    mt5_risk_api: dict[str, Any],
) -> None:
    manager = RiskManager(risk_per_symbol=0.01, max_total_risk=0.02)

    size = manager.calculate_position_size("US100.cash", stop_loss_pips=50.0)
    buy_stop = manager.calculate_stop_loss_price("US100.cash", mt5.ORDER_TYPE_BUY, 50.0)
    sell_stop = manager.calculate_stop_loss_price("US100.cash", mt5.ORDER_TYPE_SELL, 50.0)

    assert size == pytest.approx(20.0)
    assert buy_stop == pytest.approx(99.51)
    assert sell_stop == pytest.approx(100.5)
# … caller assertions omitted …
```

2. [test fixture: `test_boolean_quote_cannot_create_a_stop_price`](../../../../tests/unit/live/test_risk_manager.py#L344)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_boolean_quote_cannot_create_a_stop_price(
    mt5_risk_api: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        mt5,
        "symbol_info_tick",
        lambda _symbol: SimpleNamespace(bid=100.0, ask=True),
        raising=False,
    )
    manager = RiskManager()

    with pytest.raises(ValueError, match="Invalid ask quote"):
        manager.calculate_stop_loss_price("US100.cash", mt5.ORDER_TYPE_BUY, 50.0)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.check_risk_limits`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Check if proposed position would exceed risk limits.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.check_risk_limits` · **Source:** [integrations/mt5/domain/risk_manager.py:546](../../../../integrations/mt5/domain/risk_manager.py#L546)

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

1. [test fixture: `test_sizing_rounds_down_and_stop_price_uses_same_distance`](../../../../tests/unit/live/test_risk_manager.py#L67)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    sell_stop = manager.calculate_stop_loss_price("US100.cash", mt5.ORDER_TYPE_SELL, 50.0)

    assert size == pytest.approx(20.0)
    assert buy_stop == pytest.approx(99.51)
    assert sell_stop == pytest.approx(100.5)
    allowed, message = manager.check_risk_limits("US100.cash", size, 50.0)
    assert allowed is True
    assert "total stop risk plus reserve: 1.00%" in message
```

2. [test fixture: `test_absolute_per_symbol_cap_limits_sizing_and_risk_acceptance`](../../../../tests/unit/live/test_risk_manager.py#L92)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        max_total_risk=0.02,
        risk_per_symbol_usd_cap=900.0,
    )

    size = manager.calculate_position_size("US100.cash", stop_loss_pips=50.0)
    allowed, message = manager.check_risk_limits("US100.cash", 18.01, 50.0)

    assert size == pytest.approx(18.0)
    assert allowed is False
    assert "per-symbol limit ($900.00" in message
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.get_account_balance`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Get current account balance.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_balance` · **Source:** [integrations/mt5/domain/risk_manager.py:129](../../../../integrations/mt5/domain/risk_manager.py#L129)

**Inputs and outputs:**

- **Returns:**

  ```text
  Account balance in account currency
  ```

**Observed usage:**

1. [production caller: `calculate_position_size`](../../../../integrations/mt5/domain/risk_manager.py#L322)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                logger.error(f"Failed to get tick for {symbol}")
                return 0.0

                # Calculate risk amount if not provided
            if risk_amount is None:
                balance = self.get_account_balance()
                risk_amount = balance * self.risk_per_symbol
            if self.risk_per_symbol_usd_cap is not None:
                if self._is_boolean_number(self.risk_per_symbol_usd_cap):
                    logger.warning("Invalid absolute per-symbol risk cap for %s", symbol)
                    return 0.0
# … caller assertions omitted …
```

2. [production caller: `check_risk_limits`](../../../../integrations/mt5/domain/risk_manager.py#L560)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
        try:
            balance = self.get_account_balance()
            if not math.isfinite(balance) or balance <= 0.0:
                return False, "Account balance is unavailable or nonpositive"
            if (
                self._is_boolean_number(proposed_position_size)
                or self._is_boolean_number(stop_loss_pips)
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.get_account_equity`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Get current account equity (balance + floating P/L).

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_equity` · **Source:** [integrations/mt5/domain/risk_manager.py:149](../../../../integrations/mt5/domain/risk_manager.py#L149)

**Inputs and outputs:**

- **Returns:**

  ```text
  Account equity in account currency
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = RiskManager(...)
result = instance.get_account_equity()
```

**Lifecycle context:** This callable participates in `RiskManager`: Manage risk across multiple trading positions. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.supports_training_account_loss_guardrails`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_balance`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_equity`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_position_size`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_stop_loss_price`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_total_exposure`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.check_risk_limits`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_volatility_multiplier`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.get_total_exposure`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Get stop risk and modeled execution reserve across open positions.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_total_exposure` · **Source:** [integrations/mt5/domain/risk_manager.py:435](../../../../integrations/mt5/domain/risk_manager.py#L435)

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

1. [test fixture: `test_aggregate_limit_reserves_only_remaining_costs_for_existing_positions`](../../../../tests/unit/live/test_risk_manager.py#L152)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        max_total_risk=0.06,
        execution_slippage_points=5.0,
        commission_per_lot=2.5,
    )

    exposure = manager.get_total_exposure()
    allowed, message = manager.check_risk_limits("US100.cash", 1.0, 50.0)

    assert exposure["total_open_risk"] == pytest.approx(500.0)
    assert exposure["total_open_execution_reserve"] == pytest.approx(5025.0)
    assert exposure["total_open_risk_with_reserve"] == pytest.approx(5525.0)
# … caller assertions omitted …
```

2. [test fixture: `test_aggregate_limit_uses_open_stop_risk_not_floating_profit`](../../../../tests/unit/live/test_risk_manager.py#L193)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        profit=0.0,
    )
    monkeypatch.setattr(mt5, "positions_get", lambda: [position], raising=False)
    manager = RiskManager(risk_per_symbol=0.01, max_total_risk=0.02)

    exposure = manager.get_total_exposure()
    allowed, message = manager.check_risk_limits("US100.cash", 20.0, 50.0)

    assert exposure["total_open_risk"] == pytest.approx(1500.0)
    assert exposure["risk_unknown_positions"] == 0
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

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_volatility_multiplier` · **Source:** [integrations/mt5/domain/risk_manager.py:639](../../../../integrations/mt5/domain/risk_manager.py#L639)

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

1. [test fixture: `test_invalid_atr_cannot_increase_or_preserve_position_size`](../../../../tests/unit/live/test_risk_manager.py#L363)

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

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.supports_training_account_loss_guardrails` · **Source:** [integrations/mt5/domain/risk_manager.py:18](../../../../integrations/mt5/domain/risk_manager.py#L18)

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
