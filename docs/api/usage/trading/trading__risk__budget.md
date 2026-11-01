# Trading · `risk.budget`

This page contains 3 public callable records owned by `trading.risk.budget`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `RiskBudgetDecision`

**Kind:** class · **Status:** stable · **Owner:** `trading.risk.budget`

**Purpose:** Approved risk amount and the policy limit that constrained it.

**Exact API:** {py:obj}`trading.risk.budget.RiskBudgetDecision` · **Source:** [trading/risk/budget.py:9](../../../../trading/risk/budget.py#L9)

**Inputs and outputs:**

**Observed usage:**

1. [production caller: `approve_dynamic_risk`](../../../../trading/risk/budget.py#L66)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def approve_dynamic_risk(
    *,
    equity: float,
    risk_frac: float,
    max_agent_risk_frac: float,
    daily_capacity: float,
    account_capacity: float,
    execution_reserve_usd: float,
) -> RiskBudgetDecision:
    requested = risk_budget_from_equity(equity, risk_frac)
    policy_cap = min(
        risk_budget_from_equity(equity, max_agent_risk_frac),
        max(0.0, float(daily_capacity)),
        max(0.0, float(account_capacity)),
    )
    reserve = max(0.0, float(execution_reserve_usd))
    approved = max(0.0, min(requested, max(0.0, policy_cap - reserve)))
    return RiskBudgetDecision(requested, approved, policy_cap, reserve)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `approve_dynamic_risk`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.budget`

**Purpose:** Approve risk after applying policy, account, and execution-cost limits.

**Exact API:** {py:obj}`trading.risk.budget.approve_dynamic_risk` · **Source:** [trading/risk/budget.py:36](../../../../trading/risk/budget.py#L36)

**Inputs and outputs:**

- **Args:**

  ```text
  equity: Current account equity.
  risk_frac: Agent-requested fraction of equity to risk.
  max_agent_risk_frac: Policy cap on agent-requested risk fraction.
  daily_capacity: Remaining daily-loss capacity.
  account_capacity: Remaining total-loss capacity.
  execution_reserve_usd: Reserved amount for modeled costs.
  ```

- **Returns:**

  ```text
  Approved risk and the policy cap used to constrain it.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = approve_dynamic_risk(equity=..., risk_frac=..., max_agent_risk_frac=..., daily_capacity=..., account_capacity=..., execution_reserve_usd=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `risk_budget_from_equity`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.budget`

**Purpose:** Resolve a non-negative dollar risk request from equity and a fraction.

**Exact API:** {py:obj}`trading.risk.budget.risk_budget_from_equity` · **Source:** [trading/risk/budget.py:23](../../../../trading/risk/budget.py#L23)

**Inputs and outputs:**

- **Args:**

  ```text
  equity: Current account equity in account currency.
  risk_fraction: Numeric value used for the risk fraction.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``risk_budget_from_equity``.
  ```

**Observed usage:**

1. [test fixture: `test_trading_risk_primitives_share_risk_and_reserve_sizing`](../../../../tests/unit/trading/test_risk.py#L21)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trading_risk_primitives_share_risk_and_reserve_sizing() -> None:
    assert stop_loss_risk_usd(10.0, 2.0, 1.5, 2.0) == 60.0
    assert risk_budget_from_equity(100_000.0, 0.01) == 1_000.0
    assert risk_budget_from_equity(-100.0, 0.01) == 0.0
    assert compute_lots_with_execution_reserve(
        total_risk_budget_usd=100.0,
        equity=100_000.0,
        risk_frac=0.01,
# … caller assertions omitted …
```

2. [production caller: `approve_dynamic_risk`](../../../../trading/risk/budget.py#L58)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def approve_dynamic_risk(
    *,
    equity: float,
    risk_frac: float,
    max_agent_risk_frac: float,
    daily_capacity: float,
    account_capacity: float,
    execution_reserve_usd: float,
) -> RiskBudgetDecision:
    requested = risk_budget_from_equity(equity, risk_frac)
    policy_cap = min(
        risk_budget_from_equity(equity, max_agent_risk_frac),
        max(0.0, float(daily_capacity)),
        max(0.0, float(account_capacity)),
    )
    reserve = max(0.0, float(execution_reserve_usd))
    approved = max(0.0, min(requested, max(0.0, policy_cap - reserve)))
    return RiskBudgetDecision(requested, approved, policy_cap, reserve)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
