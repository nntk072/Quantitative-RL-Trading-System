# Integrations · `mt5.domain.risk_manager`

This page contains 9 public callable records owned by `integrations.mt5.domain.risk_manager`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `RiskManager`

**Kind:** class · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Manage risk across multiple trading positions.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager` · **Source:** [integrations/mt5/domain/risk_manager.py:10](../../../../integrations/mt5/domain/risk_manager.py#L10)

**Observed usage:**

1. [test fixture: `test_sizing_rounds_down_and_stop_price_uses_same_distance`](../../../../tests/unit/live/test_risk_manager.py#L58)

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

2. [test fixture: `test_risk_manager_constructor_defaults_match_live_config`](../../../../tests/unit/live/test_risk_manager.py#L73)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_risk_manager_constructor_defaults_match_live_config() -> None:
    manager = RiskManager()

    assert manager.risk_per_symbol == pytest.approx(0.01)
    assert manager.max_total_risk == pytest.approx(0.02)
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

1. [test fixture: `test_sizing_rounds_down_and_stop_price_uses_same_distance`](../../../../tests/unit/live/test_risk_manager.py#L58)

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

2. [test fixture: `test_risk_manager_constructor_defaults_match_live_config`](../../../../tests/unit/live/test_risk_manager.py#L73)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_risk_manager_constructor_defaults_match_live_config() -> None:
    manager = RiskManager()

    assert manager.risk_per_symbol == pytest.approx(0.01)
    assert manager.max_total_risk == pytest.approx(0.02)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.calculate_position_size`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Calculate position size based on stop loss and risk amount.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_position_size` · **Source:** [integrations/mt5/domain/risk_manager.py:151](../../../../integrations/mt5/domain/risk_manager.py#L151)

**Inputs and outputs:**

- **Args:**

  ```text
  symbol: Trading symbol
  stop_loss_pips: Stop loss in pips (or points for non-forex)
  risk_amount: Amount to risk (if None, uses risk_per_symbol * balance)
  volatility_multiplier: Multiplier to adjust for volatility (higher volatility = smaller position)
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

2. [test fixture: `test_volume_step_rounding_never_exceeds_cash_risk_budget`](../../../../tests/unit/live/test_risk_manager.py#L84)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_volume_step_rounding_never_exceeds_cash_risk_budget(
    mt5_risk_api: dict[str, Any],
) -> None:
    manager = RiskManager(risk_per_symbol=0.01, max_total_risk=0.02)

    size = manager.calculate_position_size("US100.cash", stop_loss_pips=50.0, risk_amount=999.9)
    distance = 50.0 * mt5_risk_api["info"].trade_tick_size
    planned_risk = (
        distance
        / mt5_risk_api["info"].trade_tick_size
        * mt5_risk_api["info"].trade_tick_value
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.calculate_stop_loss_price`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Build the broker-side SL using the same distance used for sizing.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_stop_loss_price` · **Source:** [integrations/mt5/domain/risk_manager.py:241](../../../../integrations/mt5/domain/risk_manager.py#L241)

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

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.check_risk_limits`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Check if proposed position would exceed risk limits.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.check_risk_limits` · **Source:** [integrations/mt5/domain/risk_manager.py:357](../../../../integrations/mt5/domain/risk_manager.py#L357)

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
    assert "total stop risk: 1.00%" in message
```

2. [test fixture: `test_aggregate_limit_uses_open_stop_risk_not_floating_profit`](../../../../tests/unit/live/test_risk_manager.py#L111)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    monkeypatch.setattr(mt5, "positions_get", lambda: [position], raising=False)
    manager = RiskManager(risk_per_symbol=0.01, max_total_risk=0.02)

    exposure = manager.get_total_exposure()
    allowed, message = manager.check_risk_limits("US100.cash", 20.0, 50.0)

    assert exposure["total_open_risk"] == pytest.approx(1500.0)
    assert exposure["risk_unknown_positions"] == 0
    assert allowed is False
    assert "2.50%" in message
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.get_account_balance`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Get current account balance.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_balance` · **Source:** [integrations/mt5/domain/risk_manager.py:31](../../../../integrations/mt5/domain/risk_manager.py#L31)

**Inputs and outputs:**

- **Returns:**

  ```text
  Account balance in account currency
  ```

**Observed usage:**

1. [production caller: `calculate_position_size`](../../../../integrations/mt5/domain/risk_manager.py#L189)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                logger.error(f"Failed to get tick for {symbol}")
                return 0.0

                # Calculate risk amount if not provided
            if risk_amount is None:
                balance = self.get_account_balance()
                risk_amount = balance * self.risk_per_symbol
            if (
                risk_amount is None
                or not math.isfinite(float(risk_amount))
                or float(risk_amount) <= 0.0
# … caller assertions omitted …
```

2. [production caller: `check_risk_limits`](../../../../integrations/mt5/domain/risk_manager.py#L371)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
        try:
            balance = self.get_account_balance()
            if not math.isfinite(balance) or balance <= 0.0:
                return False, "Account balance is unavailable or nonpositive"
            if not math.isfinite(proposed_position_size) or proposed_position_size <= 0.0:
                return False, "Proposed position size is unavailable or nonpositive"
            if (
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.get_account_equity`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Get current account equity (balance + floating P/L).

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_equity` · **Source:** [integrations/mt5/domain/risk_manager.py:47](../../../../integrations/mt5/domain/risk_manager.py#L47)

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

**Lifecycle context:** This callable participates in `RiskManager`: Manage risk across multiple trading positions. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_balance`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_equity`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_position_size`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_stop_loss_price`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_total_exposure`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.check_risk_limits`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_volatility_multiplier`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.get_total_exposure`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Get total exposure across all open positions.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_total_exposure` · **Source:** [integrations/mt5/domain/risk_manager.py:274](../../../../integrations/mt5/domain/risk_manager.py#L274)

**Inputs and outputs:**

- **Args:**

  ```text
  symbols: Optional list of symbols to filter by
  ```

- **Returns:**

  ```text
  Dictionary with exposure metrics
  ```

**Observed usage:**

1. [test fixture: `test_aggregate_limit_uses_open_stop_risk_not_floating_profit`](../../../../tests/unit/live/test_risk_manager.py#L110)

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

2. [production caller: `check_risk_limits`](../../../../integrations/mt5/domain/risk_manager.py#L401)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                    False,
                    f"Position risk ({position_risk_percent:.2%}) exceeds per-symbol limit ({self.risk_per_symbol:.2%})",
                )

                # Check total risk across all positions
            exposure = self.get_total_exposure()
            if exposure.get("query_failed") or exposure.get("risk_unknown_positions", 0):
                return False, "Existing position stop risk is unknown; refusing additional exposure"
            new_total_risk = float(exposure["total_open_risk"]) + position_risk
            new_total_risk_percent = new_total_risk / balance

# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`

## `RiskManager.get_volatility_multiplier`

**Kind:** method · **Status:** stable · **Owner:** `integrations.mt5.domain.risk_manager`

**Purpose:** Calculate the volatility multiplier for position sizing.

**Exact API:** {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_volatility_multiplier` · **Source:** [integrations/mt5/domain/risk_manager.py:422](../../../../integrations/mt5/domain/risk_manager.py#L422)

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

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = RiskManager(...)
result = instance.get_volatility_multiplier(atr_percentage=..., base_atr=...)
```

**Lifecycle context:** This callable participates in `RiskManager`: Manage risk across multiple trading positions. Related public lifecycle methods: {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_balance`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_account_equity`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_position_size`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.calculate_stop_loss_price`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_total_exposure`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.check_risk_limits`, {py:obj}`integrations.mt5.domain.risk_manager.RiskManager.get_volatility_multiplier`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/integrations/index`
