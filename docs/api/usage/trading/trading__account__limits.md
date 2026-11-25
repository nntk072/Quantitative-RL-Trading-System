# Trading · `account.limits`

This page contains 4 public callable records owned by `trading.account.limits`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `canonical_daily_loss`

**Kind:** function · **Status:** stable · **Owner:** `trading.account.limits`

**Purpose:** Return session-start equity minus current equity, floored at zero.

**Exact API:** {py:obj}`trading.account.limits.canonical_daily_loss` · **Source:** [trading/account/limits.py:6](../../../../trading/account/limits.py#L6)

**Inputs and outputs:**

- **Args:**

  ```text
  session_start_equity: Equity at the start of the current loss session.
  equity: Current account equity.
  ```

- **Returns:**

  ```text
  Nonnegative realized daily loss.
  ```

**Observed usage:**

1. [test fixture: `test_daily_loss_is_start_minus_equity_when_losing`](../../../../tests/unit/trading/test_semantic_oracle_limits_sizing.py#L24)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_daily_loss_is_start_minus_equity_when_losing() -> None:
    # 10000 - 9700 = 300
    assert canonical_daily_loss(10000.0, 9700.0) == pytest.approx(300.0)
```

2. [test fixture: `test_daily_loss_is_zero_when_equity_rose`](../../../../tests/unit/trading/test_semantic_oracle_limits_sizing.py#L29)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_daily_loss_is_zero_when_equity_rose() -> None:
    # 10000 - 10200 = -200, floored at 0
    assert canonical_daily_loss(10000.0, 10200.0) == 0.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `daily_floor`

**Kind:** function · **Status:** stable · **Owner:** `trading.account.limits`

**Purpose:** Calculate the lowest permitted equity for the daily-loss rule.

**Exact API:** {py:obj}`trading.account.limits.daily_floor` · **Source:** [trading/account/limits.py:19](../../../../trading/account/limits.py#L19)

**Inputs and outputs:**

- **Args:**

  ```text
  session_start_equity: Equity at the start of the loss session.
  daily_loss_limit: Maximum permitted daily loss in account currency.
  ```

- **Returns:**

  ```text
  Equity floor for the session.
  ```

**Observed usage:**

1. [test fixture: `test_daily_floor_is_start_minus_limit`](../../../../tests/unit/trading/test_semantic_oracle_limits_sizing.py#L34)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_daily_floor_is_start_minus_limit() -> None:
    # 10000 - 500 = 9500
    assert daily_floor(10000.0, 500.0) == pytest.approx(9500.0)
```

2. [production caller: `daily_floor`](../../../../trading/account/account_state.py#L198)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def daily_floor(self, daily_loss_limit: float) -> float:
    anchor = (
        self.session_start_balance
        if self.daily_pnl_basis == "ftmo_midnight_balance"
        else self.session_start_equity
    )
    return compute_daily_floor(anchor, daily_loss_limit)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `remaining_account_capacity`

**Kind:** function · **Status:** stable · **Owner:** `trading.account.limits`

**Purpose:** Calculate equity available above the account floor.

**Exact API:** {py:obj}`trading.account.limits.remaining_account_capacity` · **Source:** [trading/account/limits.py:48](../../../../trading/account/limits.py#L48)

**Inputs and outputs:**

- **Args:**

  ```text
  equity: Current account equity.
  account_floor: Minimum permitted account equity.
  ```

- **Returns:**

  ```text
  Nonnegative capacity above the floor.
  ```

**Observed usage:**

1. [test fixture: `test_remaining_account_capacity_above_floor_and_at_floor`](../../../../tests/unit/trading/test_semantic_oracle_limits_sizing.py#L49)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_remaining_account_capacity_above_floor_and_at_floor() -> None:
    # 9700 - 9000 = 700
    assert remaining_account_capacity(9700.0, 9000.0) == pytest.approx(700.0)
    # 8900 - 9000 = -100, floored at 0
    assert remaining_account_capacity(8900.0, 9000.0) == 0.0
```

2. [production caller: `remaining_account_capacity`](../../../../trading/account/account_state.py#L225)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def remaining_account_capacity(self, account_floor: float) -> float:
    return compute_remaining_account_capacity(self.equity, account_floor)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `remaining_daily_capacity`

**Kind:** function · **Status:** stable · **Owner:** `trading.account.limits`

**Purpose:** Calculate remaining loss capacity under the daily limit.

**Exact API:** {py:obj}`trading.account.limits.remaining_daily_capacity` · **Source:** [trading/account/limits.py:32](../../../../trading/account/limits.py#L32)

**Inputs and outputs:**

- **Args:**

  ```text
  session_start_equity: Equity at the start of the loss session.
  equity: Current account equity.
  daily_loss_limit: Maximum permitted daily loss.
  ```

- **Returns:**

  ```text
  Nonnegative remaining daily capacity.
  ```

**Observed usage:**

1. [test fixture: `test_remaining_daily_capacity_is_equity_above_the_floor`](../../../../tests/unit/trading/test_semantic_oracle_limits_sizing.py#L39)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_remaining_daily_capacity_is_equity_above_the_floor() -> None:
    # floor 9500; 9700 - 9500 = 200
    assert remaining_daily_capacity(10000.0, 9700.0, 500.0) == pytest.approx(200.0)
```

2. [test fixture: `test_remaining_daily_capacity_is_zero_once_breached`](../../../../tests/unit/trading/test_semantic_oracle_limits_sizing.py#L44)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_remaining_daily_capacity_is_zero_once_breached() -> None:
    # floor 9500; 9400 - 9500 = -100, floored at 0 (breach latch input)
    assert remaining_daily_capacity(10000.0, 9400.0, 500.0) == 0.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
