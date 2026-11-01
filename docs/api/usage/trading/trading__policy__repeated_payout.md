# Trading · `policy.repeated_payout`

This page contains 2 public callable records owned by `trading.policy.repeated_payout`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `PayoutDecision`

**Kind:** class · **Status:** stable · **Owner:** `trading.policy.repeated_payout`

**Purpose:** Result of evaluating whether an account payout is due.

**Exact API:** {py:obj}`trading.policy.repeated_payout.PayoutDecision` · **Source:** [trading/policy/repeated_payout.py:11](../../../../trading/policy/repeated_payout.py#L11)

**Inputs and outputs:**

**Observed usage:**

1. [production caller: `evaluate_payout`](../../../../trading/policy/repeated_payout.py#L37)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def evaluate_payout(
    balance: float, operating_balance: float, target_balance: float
) -> PayoutDecision:
    due = payout_due(balance, target_balance)
    return PayoutDecision(due=due, amount=payout_amount(balance, operating_balance) if due else 0.0)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `evaluate_payout`

**Kind:** function · **Status:** stable · **Owner:** `trading.policy.repeated_payout`

**Purpose:** Evaluate payout eligibility and amount for an account balance.

**Exact API:** {py:obj}`trading.policy.repeated_payout.evaluate_payout` · **Source:** [trading/policy/repeated_payout.py:23](../../../../trading/policy/repeated_payout.py#L23)

**Inputs and outputs:**

- **Args:**

  ```text
  balance: Current balance.
  operating_balance: Balance retained after a payout.
  target_balance: Balance required for payout eligibility.
  ```

- **Returns:**

  ```text
  Decision with eligibility and nonnegative payout amount.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = evaluate_payout(balance=..., operating_balance=..., target_balance=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
