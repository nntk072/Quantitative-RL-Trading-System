# Trading · `account.account_state`

This page contains 18 public callable records owned by `trading.account.account_state`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `AccountState`

**Kind:** class · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Mutable account state for the backtester / environment.

**Exact API:** {py:obj}`trading.account.account_state.AccountState` · **Source:** [trading/account/account_state.py:28](../../../../trading/account/account_state.py#L28)

**Observed usage:**

1. [test fixture: `setUp`](../../../../tests/integration/backtest/test_broker_fill_accounting.py#L13)

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

**Exact API:** {py:obj}`trading.account.account_state.AccountState` · **Source:** [trading/account/account_state.py:28](../../../../trading/account/account_state.py#L28)

**Observed usage:**

1. [test fixture: `setUp`](../../../../tests/integration/backtest/test_broker_fill_accounting.py#L13)

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

**Exact API:** {py:obj}`trading.account.account_state.AccountState.canonical_daily_loss` · **Source:** [trading/account/account_state.py:122](../../../../trading/account/account_state.py#L122)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``canonical_daily_loss``.
  ```

**Observed usage:**

1. [test fixture: `test_gross_closed_loss_counter_is_separate_from_net_daily_loss`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L163)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_gross_closed_loss_counter_is_separate_from_net_daily_loss() -> None:
    acc = AccountState(policy_mode="legacy")
    acc.close_trade(-4_000.0)
    acc.close_trade(2_500.0)
    acc.close_trade(-1_000.0)

    assert acc.equity == pytest.approx(97_500.0)
    assert acc.daily_loss == pytest.approx(5_000.0)
    assert acc.canonical_daily_loss() == pytest.approx(2_500.0)
```

2. [test fixture: `test_fixed_session_equity_daily_floor_counts_unrealized_loss`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L173)

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

**Exact API:** {py:obj}`trading.account.account_state.AccountState.close_trade` · **Source:** [trading/account/account_state.py:94](../../../../trading/account/account_state.py#L94)

**Inputs and outputs:**

- **Args:**

  ```text
  pnl: Numeric value used for the pnl.
  ```

**Observed usage:**

1. [test fixture: `test_gross_closed_loss_counter_is_separate_from_net_daily_loss`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L157)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_gross_closed_loss_counter_is_separate_from_net_daily_loss() -> None:
    acc = AccountState(policy_mode="legacy")
    acc.close_trade(-4_000.0)
    acc.close_trade(2_500.0)
    acc.close_trade(-1_000.0)

    assert acc.equity == pytest.approx(97_500.0)
    assert acc.daily_loss == pytest.approx(5_000.0)
    assert acc.canonical_daily_loss() == pytest.approx(2_500.0)
```

2. [test fixture: `test_account_state_exports_selected_daily_loss_basis_through_risk_state`](../../../../tests/unit/trading/test_risk_policy_contract.py#L21)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_account_state_exports_selected_daily_loss_basis_through_risk_state() -> None:
    legacy_mode = AccountState(policy_mode="legacy")
    legacy_mode.close_trade(-4_000.0)
    legacy_mode.close_trade(2_500.0)
    legacy_mode.close_trade(-1_000.0)
    session_state = legacy_mode.to_risk_state(daily_loss_limit=5_000.0, open_risk=125.0)

    assert session_state.daily_pnl_basis == RISK_DAILY_PNL_BASIS_SESSION_EQUITY
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.daily_floor`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Return the session equity anchor minus its fixed loss allowance.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.daily_floor` · **Source:** [trading/account/account_state.py:181](../../../../trading/account/account_state.py#L181)

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

1. [test fixture: `test_daily_loss_threshold_uses_percentage_even_in_fixed_other_limits_mode`](../../../../tests/unit/trading/test_guardrails.py#L209)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    account.balance = account.equity = 102_000.0
    account.session_start_balance = account.session_start_equity = 102_000.0

    assert guardrails.daily_limit_for(account) == pytest.approx(5_000.0)
    assert guardrails.soft_daily_limit_for(account) == pytest.approx(2_000.0)
    assert account.daily_floor(guardrails.daily_limit_for(account)) == pytest.approx(97_000.0)
```

2. [test fixture: `test_daily_percentage_floor_reanchors_to_each_session_opening_equity`](../../../../tests/unit/trading/test_guardrails.py#L244)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        limit_value_mode="percent_equity",
        daily_loss_limit_pct=0.05,
    )
    account = AccountState(initial_balance=100_000.0, policy_mode="repeated_payout")

    assert account.daily_floor(guardrails.daily_limit_for(account)) == 95_000.0
    account.equity = 95_000.0
    assert not guardrails.check_daily(account)
    account.equity = 94_999.99
    assert guardrails.check_daily(account)

# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.daily_pnl_basis`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Return the versioned daily-PnL basis used for daily risk.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.daily_pnl_basis` · **Source:** [trading/account/account_state.py:132](../../../../trading/account/account_state.py#L132)

**Inputs and outputs:**

- **Returns:**

  ```text
  The explicitly selected basis, or session equity by default.
  ```

**Observed usage:**

1. [production caller: `to_risk_state`](../../../../trading/account/account_state.py#L167)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
        from trading.risk.contracts import (
            RISK_DAILY_PNL_BASIS_SESSION_EQUITY,
            RiskState,
        )

        basis = self.daily_pnl_basis
        daily_pnl = (
            float(self.equity) - float(self.session_start_equity)
            if basis == RISK_DAILY_PNL_BASIS_SESSION_EQUITY
            else -float(self.daily_loss)
        )
# … caller assertions omitted …
```

2. [production caller: `account_state_snapshot`](../../../../trading/account/snapshots.py#L90)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "balance": float(account.balance),
        "equity": float(account.equity),
        "open_pnl": float(account.open_pnl),
        "session_start_balance": float(account.session_start_balance),
        "session_start_equity": float(account.session_start_equity),
        "daily_pnl_basis": str(account.daily_pnl_basis),
        "daily_loss": float(account.canonical_daily_loss()),
        "daily_loss_limit_usd": float(daily_loss_limit_usd),
        "soft_daily_loss_limit_usd": float(soft_daily_loss_limit_usd),
        "daily_floor_equity": float(account.daily_floor(daily_loss_limit_usd)),
        "loss_from_initial_usd": float(account.loss_from_initial()),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.drawdown_pct`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Peak loss from initial as a fraction of initial balance.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.drawdown_pct` · **Source:** [trading/account/account_state.py:273](../../../../trading/account/account_state.py#L273)

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

**Lifecycle context:** This callable participates in `AccountState`: Mutable account state for the backtester / environment. Related public lifecycle methods: {py:obj}`trading.account.account_state.AccountState.update_equity`, {py:obj}`trading.account.account_state.AccountState.close_trade`, {py:obj}`trading.account.account_state.AccountState.reset_daily`, {py:obj}`trading.account.account_state.AccountState.canonical_daily_loss`, {py:obj}`trading.account.account_state.AccountState.daily_pnl_basis`, {py:obj}`trading.account.account_state.AccountState.to_risk_state`, {py:obj}`trading.account.account_state.AccountState.daily_floor`, {py:obj}`trading.account.account_state.AccountState.remaining_daily_capacity`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.loss_from_initial`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Current absolute loss vs initial balance (0 if equity ≥ initial).

**Exact API:** {py:obj}`trading.account.account_state.AccountState.loss_from_initial` · **Source:** [trading/account/account_state.py:265](../../../../trading/account/account_state.py#L265)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``loss_from_initial``.
  ```

**Observed usage:**

1. [production caller: `_update_loss_from_initial`](../../../../trading/account/account_state.py#L76)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _update_loss_from_initial(self) -> None:
    if self.equity > self.peak_equity:
        self.peak_equity = self.equity
    loss = self.loss_from_initial()
    if loss > self.max_drawdown:
        self.max_drawdown = loss
```

2. [production caller: `account_state_snapshot`](../../../../trading/account/snapshots.py#L95)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "daily_pnl_basis": str(account.daily_pnl_basis),
        "daily_loss": float(account.canonical_daily_loss()),
        "daily_loss_limit_usd": float(daily_loss_limit_usd),
        "soft_daily_loss_limit_usd": float(soft_daily_loss_limit_usd),
        "daily_floor_equity": float(account.daily_floor(daily_loss_limit_usd)),
        "loss_from_initial_usd": float(account.loss_from_initial()),
        "max_drawdown_usd": float(account.max_drawdown),
        "max_loss_limit_usd": float(max_loss_limit_usd),
        "max_loss_floor_equity": float(max_loss_floor_equity),
        "max_drawdown_mode": str(max_drawdown_mode),
        "max_drawdown_from_reference_usd": float(max_drawdown_from_reference_usd),
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.peak_eod_drawdown_usd`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Current dollar drawdown from the last completed-session equity peak.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.peak_eod_drawdown_usd` · **Source:** [trading/account/account_state.py:303](../../../../trading/account/account_state.py#L303)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``peak_eod_drawdown_usd``.
  ```

**Observed usage:**

1. [test fixture: `test_account_state_records_drawdown_from_prior_eod_peak_once`](../../../../tests/unit/trading/test_guardrails.py#L334)

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

2. [production caller: `record_eod_equity`](../../../../trading/account/account_state.py#L297)

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

**Exact API:** {py:obj}`trading.account.account_state.AccountState.record_eod_equity` · **Source:** [trading/account/account_state.py:291](../../../../trading/account/account_state.py#L291)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``record_eod_equity``.
  ```

**Observed usage:**

1. [test fixture: `test_account_state_records_drawdown_from_prior_eod_peak_once`](../../../../tests/unit/trading/test_guardrails.py#L335)

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

**Exact API:** {py:obj}`trading.account.account_state.AccountState.remaining_account_capacity` · **Source:** [trading/account/account_state.py:205](../../../../trading/account/account_state.py#L205)

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

1. [test fixture: `test_payout_reset_reanchors_session_and_preserves_static_floor_capacity`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L202)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_payout_reset_reanchors_session_and_preserves_static_floor_capacity() -> None:
    acc = AccountState(policy_mode="repeated_payout")
    acc.balance = 110_250.0
    acc.update_equity(0.0)
    acc.reset_operating_balance(100_000.0, max_drawdown_mode="static")
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

**Purpose:** Return the remaining capacity to the strict-below session floor.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.remaining_daily_capacity` · **Source:** [trading/account/account_state.py:192](../../../../trading/account/account_state.py#L192)

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

1. [test fixture: `test_fixed_session_equity_daily_floor_counts_unrealized_loss`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L174)

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

**Purpose:** Set a new session equity anchor and clear the prior loss counter.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.reset_daily` · **Source:** [trading/account/account_state.py:116](../../../../trading/account/account_state.py#L116)

**Observed usage:**

1. [test fixture: `test_daily_percentage_floor_reanchors_to_each_session_opening_equity`](../../../../tests/unit/trading/test_guardrails.py#L251)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert not guardrails.check_daily(account)
    account.equity = 94_999.99
    assert guardrails.check_daily(account)

    account.equity = 102_000.0
    account.reset_daily()
    assert account.daily_floor(guardrails.daily_limit_for(account)) == 97_000.0
    assert guardrails.daily_limit_for(account) == 5_000.0
    account.equity = 97_000.0
    assert not guardrails.check_daily(account)
    account.equity = 96_999.99
# … caller assertions omitted …
```

2. [test fixture: `test_fixed_session_equity_daily_floor_counts_unrealized_loss`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L170)

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

## `AccountState.reset_operating_balance`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Reset account anchors after payout while preserving retained profit.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.reset_operating_balance` · **Source:** [trading/account/account_state.py:216](../../../../trading/account/account_state.py#L216)

**Inputs and outputs:**

- **Args:**

  ```text
  post_payout_balance: Account balance remaining after withdrawal.
  max_drawdown_mode: Maximum-loss mode controlling the payout floor.
  ```

**Observed usage:**

1. [test fixture: `test_payout_reanchors_daily_loss_and_locks_trailing_floor_at_initial`](../../../../tests/unit/trading/test_guardrails.py#L288)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    account = AccountState(initial_balance=100_000.0, policy_mode="repeated_payout")
    account.balance = 108_000.0
    account.update_equity(0.0)
    account.peak_eod_equity = 108_000.0

    account.reset_operating_balance(100_000.0, max_drawdown_mode=mode)

    assert account.session_start_equity == 100_000.0
    assert guardrails.daily_limit_for(account) == 5_000.0
    assert account.daily_floor(guardrails.daily_limit_for(account)) == 95_000.0
    assert not guardrails.check_max_drawdown(account)
# … caller assertions omitted …
```

2. [test fixture: `test_partial_payout_preserves_trade_buffer_above_locked_floor`](../../../../tests/unit/trading/test_guardrails.py#L316)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_partial_payout_preserves_trade_buffer_above_locked_floor(mode: str) -> None:
    account = AccountState(initial_balance=100_000.0, policy_mode="repeated_payout")
    account.balance = 105_000.0
    account.equity = 105_000.0
    account.reset_operating_balance(102_500.0, max_drawdown_mode=mode)
    guardrails = FTMOGuardrails(max_drawdown_mode=mode)  # type: ignore[arg-type]

    assert account.balance == 102_500.0
    assert account.payout_drawdown_floor == 100_000.0
    assert guardrails.max_loss_floor_for(account) == 100_000.0
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.to_array`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Return a fixed-length array for the env observation.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.to_array` · **Source:** [trading/account/account_state.py:311](../../../../trading/account/account_state.py#L311)

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

**Lifecycle context:** This callable participates in `AccountState`: Mutable account state for the backtester / environment. Related public lifecycle methods: {py:obj}`trading.account.account_state.AccountState.update_equity`, {py:obj}`trading.account.account_state.AccountState.close_trade`, {py:obj}`trading.account.account_state.AccountState.reset_daily`, {py:obj}`trading.account.account_state.AccountState.canonical_daily_loss`, {py:obj}`trading.account.account_state.AccountState.daily_pnl_basis`, {py:obj}`trading.account.account_state.AccountState.to_risk_state`, {py:obj}`trading.account.account_state.AccountState.daily_floor`, {py:obj}`trading.account.account_state.AccountState.remaining_daily_capacity`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.to_risk_state`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Build the versioned risk-policy view of the current account.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.to_risk_state` · **Source:** [trading/account/account_state.py:148](../../../../trading/account/account_state.py#L148)

**Inputs and outputs:**

- **Args:**

  ```text
  daily_loss_limit: Current hard or soft daily-loss threshold.
  open_risk: Risk already committed to open positions.
  ```

- **Returns:**

  ```text
  A validated ``risk-state-v1`` account snapshot.
  ```

**Observed usage:**

1. [test fixture: `test_account_state_exports_selected_daily_loss_basis_through_risk_state`](../../../../tests/unit/trading/test_risk_policy_contract.py#L24)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_account_state_exports_selected_daily_loss_basis_through_risk_state() -> None:
    legacy_mode = AccountState(policy_mode="legacy")
    legacy_mode.close_trade(-4_000.0)
    legacy_mode.close_trade(2_500.0)
    legacy_mode.close_trade(-1_000.0)
    session_state = legacy_mode.to_risk_state(daily_loss_limit=5_000.0, open_risk=125.0)

    assert session_state.daily_pnl_basis == RISK_DAILY_PNL_BASIS_SESSION_EQUITY
    assert session_state.daily_pnl == -2_500.0
    assert session_state.open_risk == 125.0
    assert legacy_mode.canonical_daily_loss() == 2_500.0
# … caller assertions omitted …
```

2. [test fixture: `test_account_state_rejects_unknown_policy_mode`](../../../../tests/unit/trading/test_risk_policy_contract.py#L57)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_account_state_rejects_unknown_policy_mode() -> None:
    import pytest

    account = AccountState(policy_mode="unsupported")

    with pytest.raises(ValueError, match="unknown account policy mode"):
        account.to_risk_state(daily_loss_limit=5_000.0)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.trailing_drawdown_pct`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Current drawdown from peak equity (HWM) as a fraction of peak.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.trailing_drawdown_pct` · **Source:** [trading/account/account_state.py:281](../../../../trading/account/account_state.py#L281)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``trailing_drawdown_pct``.
  ```

**Observed usage:**

1. [production caller: `account_state_snapshot`](../../../../trading/account/snapshots.py#L110)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "max_peak_eod_drawdown_usd": float(account.max_peak_eod_drawdown_usd),
        "payout_drawdown_floor": (
            None if account.payout_drawdown_floor is None else float(account.payout_drawdown_floor)
        ),
        "trailing_drawdown_usd": max(0.0, float(account.peak_equity) - float(account.equity)),
        "trailing_drawdown_fraction": float(account.trailing_drawdown_pct()),
        "trailing_drawdown_limit_usd": float(trailing_drawdown_limit_usd),
        "soft_trailing_drawdown_limit_usd": float(soft_trailing_drawdown_limit_usd),
        "risk_per_trade_limit_usd": float(risk_per_trade_limit_usd),
        "position_direction": direction,
        "position_size": size,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `AccountState.update_equity`

**Kind:** method · **Status:** stable · **Owner:** `trading.account.account_state`

**Purpose:** Recompute equity from balance + unrealised P&L.

**Exact API:** {py:obj}`trading.account.account_state.AccountState.update_equity` · **Source:** [trading/account/account_state.py:80](../../../../trading/account/account_state.py#L80)

**Inputs and outputs:**

- **Args:**

  ```text
  open_pnl: Numeric value used for the open pnl.
  ```

**Observed usage:**

1. [test fixture: `test_max_loss_not_trailing_hwm`](../../../../tests/unit/trading/test_guardrails.py#L114)

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
    assert not g.check_max_drawdown(acc)
    acc.balance = 100_000.0
    acc.update_equity(-10_000.01)
    assert g.check_max_drawdown(acc)
```

2. [test fixture: `test_payout_reanchors_daily_loss_and_locks_trailing_floor_at_initial`](../../../../tests/unit/trading/test_guardrails.py#L285)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        max_loss_limit_initial_pct=0.10,
        max_drawdown_mode=mode,  # type: ignore[arg-type]
    )
    account = AccountState(initial_balance=100_000.0, policy_mode="repeated_payout")
    account.balance = 108_000.0
    account.update_equity(0.0)
    account.peak_eod_equity = 108_000.0

    account.reset_operating_balance(100_000.0, max_drawdown_mode=mode)

    assert account.session_start_equity == 100_000.0
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
