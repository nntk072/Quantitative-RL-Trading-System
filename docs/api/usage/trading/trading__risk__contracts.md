# Trading · `risk.contracts`

This page contains 4 public callable records owned by `trading.risk.contracts`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `RiskDecision`

**Kind:** class · **Status:** stable · **Owner:** `trading.risk.contracts`

**Purpose:** Risk-policy result for one requested trade.

**Exact API:** {py:obj}`trading.risk.contracts.RiskDecision` · **Source:** [trading/risk/contracts.py:26](../../../../trading/risk/contracts.py#L26)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `decide`](../../../../tests/unit/trading/test_risk_policy_contract.py#L15)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def decide(self, state: RiskState, requested_risk: float) -> RiskDecision:
    del state
    amount = min(requested_risk, self.cap)
    return RiskDecision(allowed=amount > 0.0, risk_amount=amount)
```

2. [test fixture: `test_two_risk_policies_consume_the_same_semantic_state`](../../../../tests/unit/trading/test_risk_policy_contract.py#L34)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_two_risk_policies_consume_the_same_semantic_state() -> None:
    state = RiskState(equity=100_000.0, daily_pnl=-400.0, open_risk=100.0, daily_loss_limit=500.0)
    policies: tuple[RiskPolicy, ...] = (_FixedCapPolicy(50.0), _DailyLossPolicy())

    decisions = tuple(policy.decide(state, requested_risk=200.0) for policy in policies)

    assert decisions == (
        RiskDecision(True, 50.0),
        RiskDecision(False, 0.0, "daily_loss_limit"),
    )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `RiskPolicy`

**Kind:** class · **Status:** stable · **Owner:** `trading.risk.contracts`

**Purpose:** Evaluate requested risk without depending on a broker or policy model.

**Exact API:** {py:obj}`trading.risk.contracts.RiskPolicy` · **Source:** [trading/risk/contracts.py:39](../../../../trading/risk/contracts.py#L39)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = RiskPolicy(...)
```

**Lifecycle context:** Evaluate requested risk without depending on a broker or policy model.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `RiskState`

**Kind:** class · **Status:** stable · **Owner:** `trading.risk.contracts`

**Purpose:** Account risk state provided to a risk policy.

**Exact API:** {py:obj}`trading.risk.contracts.RiskState` · **Source:** [trading/risk/contracts.py:10](../../../../trading/risk/contracts.py#L10)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `test_two_risk_policies_consume_the_same_semantic_state`](../../../../tests/unit/trading/test_risk_policy_contract.py#L28)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_two_risk_policies_consume_the_same_semantic_state() -> None:
    state = RiskState(equity=100_000.0, daily_pnl=-400.0, open_risk=100.0, daily_loss_limit=500.0)
    policies: tuple[RiskPolicy, ...] = (_FixedCapPolicy(50.0), _DailyLossPolicy())

    decisions = tuple(policy.decide(state, requested_risk=200.0) for policy in policies)

    assert decisions == (
        RiskDecision(True, 50.0),
        RiskDecision(False, 0.0, "daily_loss_limit"),
    )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `RiskPolicy.decide`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.contracts`

**Purpose:** Evaluate requested risk against the current account state.

**Exact API:** {py:obj}`trading.risk.contracts.RiskPolicy.decide` · **Source:** [trading/risk/contracts.py:42](../../../../trading/risk/contracts.py#L42)

**Inputs and outputs:**

- **Args:**

  ```text
  state: Current account and open-risk state.
  requested_risk: Agent-requested risk amount.
  ```

- **Returns:**

  ```text
  Approved risk decision and any policy reason.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = RiskPolicy(...)
result = instance.decide(state=..., requested_risk=...)
```

**Lifecycle context:** This callable participates in `RiskPolicy`: Evaluate requested risk without depending on a broker or policy model. Related public lifecycle methods: {py:obj}`trading.risk.contracts.RiskPolicy.decide`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
