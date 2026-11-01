# Trading · `account.account_state`

This page contains 16 public callable records owned by `trading.account.account_state`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `AccountState`

**Kind:** class · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Mutable account state for the backtester / environment.

**Exact API:** {py:obj}`trading.account.account_state.AccountState` · **Source:** [trading/account/account_state.py:26](../../../../trading/account/account_state.py#L26)

**Observed usage:**

1. [test fixture: `setUp`](../../../../tests/integration/backtest/test_broker_fill_accounting.py#L12)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def setUp(self):
    self.acc = AccountState(initial_balance=100_000.0)
    self.broker = Broker(cost_model=CostModel(commission_per_lot=2.0))
```

2. [test fixture: `test_mirrored_long_short_round_trip_and_mark_to_market`](../../../../tests/integration/backtest/test_broker_quote_parity.py#L15)

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
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState`

**Kind:** class · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Mutable account state for the backtester / environment.

**Exact API:** {py:obj}`trading.account.account_state.AccountState` · **Source:** [trading/account/account_state.py:26](../../../../trading/account/account_state.py#L26)

**Observed usage:**

1. [test fixture: `setUp`](../../../../tests/integration/backtest/test_broker_fill_accounting.py#L12)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def setUp(self):
    self.acc = AccountState(initial_balance=100_000.0)
    self.broker = Broker(cost_model=CostModel(commission_per_lot=2.0))
```

2. [test fixture: `test_mirrored_long_short_round_trip_and_mark_to_market`](../../../../tests/integration/backtest/test_broker_quote_parity.py#L15)

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
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.canonical_daily_loss`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Daily loss used by the selected policy.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.canonical_daily_loss` · **Source:** [trading/account/account_state.py:93](../../../../trading/account/account_state.py#L93)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``canonical_daily_loss``.
  ```

**Observed usage:**

1. [test fixture: `test_fixed_session_equity_daily_floor_counts_unrealized_loss`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L31)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fixed_session_equity_daily_floor_counts_unrealized_loss() -> None:
    acc = AccountState(policy_mode="repeated_payout")
    acc.balance = 108_000.0
    acc.update_equity(0.0)
    acc.reset_daily()
    assert acc.daily_floor(5_000.0) == 103_000.0
    acc.update_equity(-2_000.0)
    assert acc.canonical_daily_loss() == 2_000.0
    assert acc.remaining_daily_capacity(5_000.0) == 3_000.0
    acc.update_equity(3_000.0)
    assert acc.daily_floor(5_000.0) == 103_000.0
    assert acc.canonical_daily_loss() == 0.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.close_trade`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Realise P&L from a closed trade.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.close_trade` · **Source:** [trading/account/account_state.py:73](../../../../trading/account/account_state.py#L73)

**Inputs and outputs:**

- **Args:**

  ```text
  pnl: Numeric value used for the pnl.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = AccountState(...)
result = instance.close_trade(pnl=...)
```

**Lifecycle context:** This callable participates in `AccountState`: Mutable account state for the backtester / environment. Related public lifecycle methods: {py:obj}`trading.account.account_state.AccountState.update_equity`, {py:obj}`trading.account.account_state.AccountState.close_trade`, {py:obj}`trading.account.account_state.AccountState.reset_daily`, {py:obj}`trading.account.account_state.AccountState.canonical_daily_loss`, {py:obj}`trading.account.account_state.AccountState.daily_floor`, {py:obj}`trading.account.account_state.AccountState.remaining_daily_capacity`, {py:obj}`trading.account.account_state.AccountState.remaining_account_capacity`, {py:obj}`trading.account.account_state.AccountState.reset_operating_balance`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.daily_floor`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Fixed session floor for repeated-payout mode.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.daily_floor` · **Source:** [trading/account/account_state.py:103](../../../../trading/account/account_state.py#L103)

**Inputs and outputs:**

- **Args:**

  ```text
  daily_loss_limit: Numeric value used for the daily loss limit.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``daily_floor``.
  ```

**Observed usage:**

1. [test fixture: `test_fixed_session_equity_daily_floor_counts_unrealized_loss`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L29)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fixed_session_equity_daily_floor_counts_unrealized_loss() -> None:
    acc = AccountState(policy_mode="repeated_payout")
    acc.balance = 108_000.0
    acc.update_equity(0.0)
    acc.reset_daily()
    assert acc.daily_floor(5_000.0) == 103_000.0
    acc.update_equity(-2_000.0)
    assert acc.canonical_daily_loss() == 2_000.0
    assert acc.remaining_daily_capacity(5_000.0) == 3_000.0
    acc.update_equity(3_000.0)
    assert acc.daily_floor(5_000.0) == 103_000.0
    assert acc.canonical_daily_loss() == 0.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.drawdown_pct`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Peak loss from initial as a fraction of initial balance.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.drawdown_pct` · **Source:** [trading/account/account_state.py:160](../../../../trading/account/account_state.py#L160)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``drawdown_pct``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = AccountState(...)
result = instance.drawdown_pct()
```

**Lifecycle context:** This callable participates in `AccountState`: Mutable account state for the backtester / environment. Related public lifecycle methods: {py:obj}`trading.account.account_state.AccountState.update_equity`, {py:obj}`trading.account.account_state.AccountState.close_trade`, {py:obj}`trading.account.account_state.AccountState.reset_daily`, {py:obj}`trading.account.account_state.AccountState.canonical_daily_loss`, {py:obj}`trading.account.account_state.AccountState.daily_floor`, {py:obj}`trading.account.account_state.AccountState.remaining_daily_capacity`, {py:obj}`trading.account.account_state.AccountState.remaining_account_capacity`, {py:obj}`trading.account.account_state.AccountState.reset_operating_balance`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.loss_from_initial`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Current absolute loss vs initial balance (0 if equity ≥ initial).

**Exact API:** {py:obj}`trading.account.account_state.AccountState.loss_from_initial` · **Source:** [trading/account/account_state.py:152](../../../../trading/account/account_state.py#L152)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``loss_from_initial``.
  ```

**Observed usage:**

1. [production caller: `_update_loss_from_initial`](../../../../trading/account/account_state.py#L59)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _update_loss_from_initial(self) -> None:
    if self.equity > self.peak_equity:
        self.peak_equity = self.equity
    loss = self.loss_from_initial()
    if loss > self.max_drawdown:
        self.max_drawdown = loss
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.peak_eod_drawdown_usd`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Current dollar drawdown from the last completed-session equity peak.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.peak_eod_drawdown_usd` · **Source:** [trading/account/account_state.py:190](../../../../trading/account/account_state.py#L190)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``peak_eod_drawdown_usd``.
  ```

**Observed usage:**

1. [test fixture: `test_account_state_records_drawdown_from_prior_eod_peak_once`](../../../../tests/unit/trading/test_guardrails.py#L104)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_account_state_records_drawdown_from_prior_eod_peak_once() -> None:
    acc = AccountState(initial_balance=100_000.0)
    acc.peak_eod_equity = 110_000.0
    acc.equity = 95_000.0

    assert acc.peak_eod_drawdown_usd == 15_000.0
    assert acc.record_eod_equity() == 15_000.0
    assert acc.max_peak_eod_drawdown_usd == 15_000.0
    assert acc.peak_eod_equity == 110_000.0

    acc.equity = 111_000.0
    assert acc.peak_eod_drawdown_usd == 0.0
    assert acc.record_eod_equity() == 0.0
    assert acc.peak_eod_equity == 111_000.0
```

2. [production caller: `record_eod_equity`](../../../../trading/account/account_state.py#L184)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def record_eod_equity(self) -> float:
    drawdown_usd = self.peak_eod_drawdown_usd
    self.max_peak_eod_drawdown_usd = max(self.max_peak_eod_drawdown_usd, drawdown_usd)
    self.peak_eod_equity = max(self.peak_eod_equity, self.equity)
    return drawdown_usd
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.record_eod_equity`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Record end-of-session equity and return drawdown from the prior EOD peak.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.record_eod_equity` · **Source:** [trading/account/account_state.py:178](../../../../trading/account/account_state.py#L178)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``record_eod_equity``.
  ```

**Observed usage:**

1. [test fixture: `test_account_state_records_drawdown_from_prior_eod_peak_once`](../../../../tests/unit/trading/test_guardrails.py#L105)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_account_state_records_drawdown_from_prior_eod_peak_once() -> None:
    acc = AccountState(initial_balance=100_000.0)
    acc.peak_eod_equity = 110_000.0
    acc.equity = 95_000.0

    assert acc.peak_eod_drawdown_usd == 15_000.0
    assert acc.record_eod_equity() == 15_000.0
    assert acc.max_peak_eod_drawdown_usd == 15_000.0
    assert acc.peak_eod_equity == 110_000.0

    acc.equity = 111_000.0
    assert acc.peak_eod_drawdown_usd == 0.0
    assert acc.record_eod_equity() == 0.0
    assert acc.peak_eod_equity == 111_000.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.remaining_account_capacity`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Return equity capacity above the account floor.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.remaining_account_capacity` · **Source:** [trading/account/account_state.py:127](../../../../trading/account/account_state.py#L127)

**Inputs and outputs:**

- **Args:**

  ```text
  account_floor: Minimum permitted account equity.
  ```

- **Returns:**

  ```text
  Nonnegative remaining account capacity.
  ```

**Observed usage:**

1. [test fixture: `test_payout_reset_reanchors_session_and_preserves_static_floor_capacity`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L58)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_payout_reset_reanchors_session_and_preserves_static_floor_capacity() -> None:
    acc = AccountState(policy_mode="repeated_payout")
    acc.balance = 110_250.0
    acc.update_equity(0.0)
    acc.reset_operating_balance(100_000.0)
    assert acc.balance == 100_000.0
    assert acc.equity == 100_000.0
    assert acc.session_start_equity == 100_000.0
    assert acc.remaining_account_capacity(90_000.0) == 10_000.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.remaining_daily_capacity`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Return the remaining capacity before the daily loss limit is breached.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.remaining_daily_capacity` · **Source:** [trading/account/account_state.py:114](../../../../trading/account/account_state.py#L114)

**Inputs and outputs:**

- **Args:**

  ```text
  daily_loss_limit: Maximum daily loss in account currency.
  ```

- **Returns:**

  ```text
  Nonnegative remaining daily capacity.
  ```

**Observed usage:**

1. [test fixture: `test_fixed_session_equity_daily_floor_counts_unrealized_loss`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L32)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fixed_session_equity_daily_floor_counts_unrealized_loss() -> None:
    acc = AccountState(policy_mode="repeated_payout")
    acc.balance = 108_000.0
    acc.update_equity(0.0)
    acc.reset_daily()
    assert acc.daily_floor(5_000.0) == 103_000.0
    acc.update_equity(-2_000.0)
    assert acc.canonical_daily_loss() == 2_000.0
    assert acc.remaining_daily_capacity(5_000.0) == 3_000.0
    acc.update_equity(3_000.0)
    assert acc.daily_floor(5_000.0) == 103_000.0
    assert acc.canonical_daily_loss() == 0.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.reset_daily`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Anchor a new session without changing legacy accounting semantics.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.reset_daily` · **Source:** [trading/account/account_state.py:87](../../../../trading/account/account_state.py#L87)

**Observed usage:**

1. [test fixture: `test_fixed_session_equity_daily_floor_counts_unrealized_loss`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L28)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fixed_session_equity_daily_floor_counts_unrealized_loss() -> None:
    acc = AccountState(policy_mode="repeated_payout")
    acc.balance = 108_000.0
    acc.update_equity(0.0)
    acc.reset_daily()
    assert acc.daily_floor(5_000.0) == 103_000.0
    acc.update_equity(-2_000.0)
    assert acc.canonical_daily_loss() == 2_000.0
    assert acc.remaining_daily_capacity(5_000.0) == 3_000.0
    acc.update_equity(3_000.0)
    assert acc.daily_floor(5_000.0) == 103_000.0
    assert acc.canonical_daily_loss() == 0.0
```

2. [test fixture: `test_repeated_daily_guardrail_uses_fixed_anchor`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L42)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_repeated_daily_guardrail_uses_fixed_anchor() -> None:
    acc = AccountState(policy_mode="repeated_payout")
    acc.balance = 108_000.0
    acc.update_equity(0.0)
    acc.reset_daily()
    guard = FTMOGuardrails(daily_loss_limit=5_000.0)
    acc.update_equity(-4_999.0)
    assert not guard.check_daily(acc)
    acc.update_equity(-5_000.0)
    assert guard.check_daily(acc)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.reset_operating_balance`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Reset deployable capital after a payout while preserving global counters elsewhere.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.reset_operating_balance` · **Source:** [trading/account/account_state.py:138](../../../../trading/account/account_state.py#L138)

**Inputs and outputs:**

- **Args:**

  ```text
  operating_balance: Numeric value used for the operating balance.
  ```

**Observed usage:**

1. [test fixture: `test_payout_reset_reanchors_session_and_preserves_static_floor_capacity`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L54)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_payout_reset_reanchors_session_and_preserves_static_floor_capacity() -> None:
    acc = AccountState(policy_mode="repeated_payout")
    acc.balance = 110_250.0
    acc.update_equity(0.0)
    acc.reset_operating_balance(100_000.0)
    assert acc.balance == 100_000.0
    assert acc.equity == 100_000.0
    assert acc.session_start_equity == 100_000.0
    assert acc.remaining_account_capacity(90_000.0) == 10_000.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.to_array`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Return a fixed-length array for the env observation.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.to_array` · **Source:** [trading/account/account_state.py:198](../../../../trading/account/account_state.py#L198)

**Inputs and outputs:**

- **Returns:**

  ```text
  Values returned by ``to_array``, in the declared order.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = AccountState(...)
result = instance.to_array()
```

**Lifecycle context:** This callable participates in `AccountState`: Mutable account state for the backtester / environment. Related public lifecycle methods: {py:obj}`trading.account.account_state.AccountState.update_equity`, {py:obj}`trading.account.account_state.AccountState.close_trade`, {py:obj}`trading.account.account_state.AccountState.reset_daily`, {py:obj}`trading.account.account_state.AccountState.canonical_daily_loss`, {py:obj}`trading.account.account_state.AccountState.daily_floor`, {py:obj}`trading.account.account_state.AccountState.remaining_daily_capacity`, {py:obj}`trading.account.account_state.AccountState.remaining_account_capacity`, {py:obj}`trading.account.account_state.AccountState.reset_operating_balance`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.trailing_drawdown_pct`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Current drawdown from peak equity (HWM) as a fraction of peak.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.trailing_drawdown_pct` · **Source:** [trading/account/account_state.py:168](../../../../trading/account/account_state.py#L168)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``trailing_drawdown_pct``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = AccountState(...)
result = instance.trailing_drawdown_pct()
```

**Lifecycle context:** This callable participates in `AccountState`: Mutable account state for the backtester / environment. Related public lifecycle methods: {py:obj}`trading.account.account_state.AccountState.update_equity`, {py:obj}`trading.account.account_state.AccountState.close_trade`, {py:obj}`trading.account.account_state.AccountState.reset_daily`, {py:obj}`trading.account.account_state.AccountState.canonical_daily_loss`, {py:obj}`trading.account.account_state.AccountState.daily_floor`, {py:obj}`trading.account.account_state.AccountState.remaining_daily_capacity`, {py:obj}`trading.account.account_state.AccountState.remaining_account_capacity`, {py:obj}`trading.account.account_state.AccountState.reset_operating_balance`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.update_equity`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Recompute equity from balance + unrealised P&L.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.update_equity` · **Source:** [trading/account/account_state.py:63](../../../../trading/account/account_state.py#L63)

**Inputs and outputs:**

- **Args:**

  ```text
  open_pnl: Numeric value used for the open pnl.
  ```

**Observed usage:**

1. [test fixture: `test_max_loss_not_trailing_hwm`](../../../../tests/unit/trading/test_guardrails.py#L43)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_max_loss_not_trailing_hwm():
    g = FTMOGuardrails(max_loss_limit=10_000.0, trailing_dd_limit=0.0)
    acc = AccountState(initial_balance=100_000.0)
    acc.update_equity(8_000.0)  # peak 108k
    acc.balance = 100_000.0
    acc.update_equity(-5_000.0)  # equity 95k — only $5k from initial
    assert not g.check_max_drawdown(acc)
    acc.balance = 100_000.0
    acc.update_equity(-10_000.0)  # equity 90k
    assert g.check_max_drawdown(acc)
```

2. [test fixture: `test_trailing_dd_is_dollar_from_peak_not_pct_of_peak`](../../../../tests/unit/trading/test_guardrails.py#L128)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trailing_dd_is_dollar_from_peak_not_pct_of_peak():
    g = FTMOGuardrails(trailing_dd_limit=0.07, max_loss_limit=10_000.0)
    acc = AccountState(initial_balance=100_000.0)
    acc.update_equity(30_000.0)  # peak 130k
    acc.balance = 123_500.0
    acc.update_equity(0.0)  # $6.5k off peak — under $7k train cap
    assert not g.check_trailing_dd(acc)
    acc.balance = 122_000.0
    acc.update_equity(0.0)  # $8k off peak — over $7k train cap
    assert g.check_trailing_dd(acc)
    assert g.breach_reason(acc) == "trailing_dd"
    # 7% of $130k peak would wait until ~$120.9k; still above that here.
    assert acc.equity > 0.93 * acc.peak_equity
    assert not g.check_max_drawdown(acc)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
