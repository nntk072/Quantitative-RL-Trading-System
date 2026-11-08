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

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = canonical_daily_loss(session_start_equity=..., equity=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

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

1. [production caller: `daily_floor`](../../../../trading/account/account_state.py#L198)

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

2. [production caller: `remaining_daily_capacity`](../../../../trading/account/limits.py#L45)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def remaining_daily_capacity(
    session_start_equity: float, equity: float, daily_loss_limit: float
) -> float:
    return max(0.0, float(equity) - daily_floor(session_start_equity, daily_loss_limit))
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

1. [production caller: `remaining_account_capacity`](../../../../trading/account/account_state.py#L225)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def remaining_account_capacity(self, account_floor: float) -> float:
    return compute_remaining_account_capacity(self.equity, account_floor)
```

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

1. [production caller: `remaining_daily_capacity`](../../../../trading/account/account_state.py#L214)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def remaining_daily_capacity(self, daily_loss_limit: float) -> float:
    anchor = (
        self.session_start_balance
        if self.daily_pnl_basis == "ftmo_midnight_balance"
        else self.session_start_equity
    )
    return compute_remaining_daily_capacity(anchor, self.equity, daily_loss_limit)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
