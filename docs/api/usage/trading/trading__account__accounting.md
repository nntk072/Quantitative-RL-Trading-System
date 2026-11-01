# Trading · `account.accounting`

This page contains 2 public callable records owned by `trading.account.accounting`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `payout_amount`

**Kind:** function · **Status:** stable · **Owner:** `trading.account.accounting`

**Purpose:** Calculate funds distributable while preserving operating balance.

**Exact API:** {py:obj}`trading.account.accounting.payout_amount` · **Source:** [trading/account/accounting.py:19](../../../../trading/account/accounting.py#L19)

**Inputs and outputs:**

- **Args:**

  ```text
  balance: Current account balance.
  operating_balance: Balance retained in the trading account.
  ```

- **Returns:**

  ```text
  Nonnegative amount available for payout.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = payout_amount(balance=..., operating_balance=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `payout_due`

**Kind:** function · **Status:** stable · **Owner:** `trading.account.accounting`

**Purpose:** Return whether balance has reached the payout target.

**Exact API:** {py:obj}`trading.account.accounting.payout_due` · **Source:** [trading/account/accounting.py:6](../../../../trading/account/accounting.py#L6)

**Inputs and outputs:**

- **Args:**

  ```text
  balance: Current account balance.
  target_balance: Balance threshold that enables a payout.
  ```

- **Returns:**

  ```text
  Whether payout due meets the requested condition.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = payout_due(balance=..., target_balance=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
