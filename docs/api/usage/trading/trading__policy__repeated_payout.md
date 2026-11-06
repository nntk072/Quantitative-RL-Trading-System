# Trading · `policy.repeated_payout`

This page contains 3 public callable records owned by `trading.policy.repeated_payout`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `PayoutDecision`

**Kind:** class · **Status:** stable · **Owner:** `trading.policy.repeated_payout`

**Purpose:** Result of evaluating whether an account payout is due.

**Exact API:** {py:obj}`trading.policy.repeated_payout.PayoutDecision` · **Source:** [trading/policy/repeated_payout.py:13](../../../../trading/policy/repeated_payout.py#L13)

**Inputs and outputs:**

**Observed usage:**

1. [production caller: `evaluate_payout`](../../../../trading/policy/repeated_payout.py#L48)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def evaluate_payout(
    balance: float,
    operating_balance: float,
    target_balance: float,
    *,
    payout_fraction: float = 1.0,
) -> PayoutDecision:
    fraction = float(payout_fraction)
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("payout_fraction must be in [0, 1]")
    due = payout_due(balance, target_balance)
    amount = payout_amount(balance, operating_balance) * fraction if due else 0.0
    return PayoutDecision(due=due, amount=amount)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `build_payout_reset_event`

**Kind:** function · **Status:** stable · **Owner:** `trading.policy.repeated_payout`

**Purpose:** Build the shared realized-balance payout event when a flat cycle qualifies.

**Exact API:** {py:obj}`trading.policy.repeated_payout.build_payout_reset_event` · **Source:** [trading/policy/repeated_payout.py:51](../../../../trading/policy/repeated_payout.py#L51)

**Inputs and outputs:**

- **Args:**

  ```text
  balance: Realized account balance at the cycle boundary.
  policy: Repeated-payout thresholds and operating balance.
  cycle: Current payout-cycle number.
  event_time: Timestamp assigned to the payout event.
  max_drawdown_mode: Maximum-loss model controlling payout share.
  ```

- **Returns:**

  ```text
  Payout reset record when due, or ``None`` when policy or balance is ineligible.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = build_payout_reset_event(balance=..., policy=..., cycle=..., event_time=..., max_drawdown_mode=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `evaluate_payout`

**Kind:** function · **Status:** stable · **Owner:** `trading.policy.repeated_payout`

**Purpose:** Evaluate payout eligibility and amount for an account balance.

**Exact API:** {py:obj}`trading.policy.repeated_payout.evaluate_payout` · **Source:** [trading/policy/repeated_payout.py:25](../../../../trading/policy/repeated_payout.py#L25)

**Inputs and outputs:**

- **Args:**

  ```text
  balance: Current balance.
  operating_balance: Balance retained after a payout.
  target_balance: Balance required for payout eligibility.
  payout_fraction: Share of realized profit paid out when eligible.
  ```

- **Returns:**

  ```text
  Decision with eligibility and nonnegative payout amount.
  ```

**Observed usage:**

1. [production caller: `build_payout_reset_event`](../../../../trading/policy/repeated_payout.py#L80)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    if not policy.repeated_payout:
        return None
    if max_drawdown_mode not in {"static", "eod", "intraday_trailing"}:
        raise ValueError("unsupported max_drawdown_mode for payout")
    payout_fraction = 1.0 if max_drawdown_mode == "static" else 0.5
    decision = evaluate_payout(
        balance,
        policy.operating_balance,
        policy.profit_target_balance,
        payout_fraction=payout_fraction,
    )
    if not decision.due:
        return None
    profit = float(balance) - float(policy.operating_balance)
    payout = float(decision.amount)
    post_payout_balance = float(balance) - payout
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
