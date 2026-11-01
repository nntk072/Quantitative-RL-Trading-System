# Trading · `risk.guardrails`

This page contains 14 public callable records owned by `trading.risk.guardrails`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `FTMOGuardrails`

**Kind:** class · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Training-compatible account guardrails for daily and total loss limits.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails` · **Source:** [trading/risk/guardrails.py:21](../../../../trading/risk/guardrails.py#L21)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `_env_stub`](../../../../tests/unit/simulation/test_environment/test_fixed_risk_sizing.py#L56)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    stub.account = _Account(equity, float(initial_balance))
    stub.contract_size = kw.get("contract_size", 1.0)
    stub.min_lot = kw.get("min_lot", 0.01)
    stub.max_lot = kw.get("max_lot", 100.0)
    stub.max_loss_per_trade_usd = kw.get("max_loss_per_trade_usd", 900.0)
    stub.guardrails = kw.get("guardrails", FTMOGuardrails())
    stub.cost_model = kw.get("cost_model", CostModel())
    for name in (
        "_sizing_equity",
        "_risk_budget_usd",
        "_risk_band_action_unit",
# … caller assertions omitted …
```

2. [test fixture: `test_dynamic_percentage_limit_uses_current_equity_and_the_900_ceiling`](../../../../tests/unit/simulation/test_environment/test_fixed_risk_sizing.py#L172)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_dynamic_percentage_limit_uses_current_equity_and_the_900_ceiling() -> None:
    percent_policy = FTMOGuardrails(
        limit_value_mode="percent_equity",
        risk_per_trade_limit_pct=0.01,
    )
    env = _env_stub(
        "dynamic",
        0.0,
        equity=40_000.0,
        initial_balance=100_000.0,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.any_breach`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return whether any configured account guardrail is breached.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.any_breach` · **Source:** [trading/risk/guardrails.py:210](../../../../trading/risk/guardrails.py#L210)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Current account state to evaluate.
  ```

- **Returns:**

  ```text
  True when a daily, total-loss, or trade-risk limit is exceeded.
  ```

**Observed usage:**

1. [test fixture: `test_no_breach`](../../../../tests/unit/trading/test_guardrails.py#L19)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_no_breach():
    g = FTMOGuardrails()
    acc = _make(daily_loss=1000.0, max_dd=500.0)
    assert not g.any_breach(acc)
    assert g.breach_reason(acc) is None
```

2. [test fixture: `test_daily_loss_breach`](../../../../tests/unit/trading/test_guardrails.py#L27)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_daily_loss_breach():
    g = FTMOGuardrails(daily_loss_limit=5000.0)
    acc = _make(daily_loss=5000.0)
    assert g.check_daily(acc)
    assert g.any_breach(acc)
    assert g.breach_reason(acc) == "daily_loss"
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.breach_reason`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return the first breached guardrail name, or None when all pass.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.breach_reason` · **Source:** [trading/risk/guardrails.py:221](../../../../trading/risk/guardrails.py#L221)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Current account state to evaluate.
  ```

- **Returns:**

  ```text
  Stable reason code for the first breach, otherwise None.
  ```

**Observed usage:**

1. [test fixture: `test_no_breach`](../../../../tests/unit/trading/test_guardrails.py#L20)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_no_breach():
    g = FTMOGuardrails()
    acc = _make(daily_loss=1000.0, max_dd=500.0)
    assert not g.any_breach(acc)
    assert g.breach_reason(acc) is None
```

2. [test fixture: `test_daily_loss_breach`](../../../../tests/unit/trading/test_guardrails.py#L28)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_daily_loss_breach():
    g = FTMOGuardrails(daily_loss_limit=5000.0)
    acc = _make(daily_loss=5000.0)
    assert g.check_daily(acc)
    assert g.any_breach(acc)
    assert g.breach_reason(acc) == "daily_loss"
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.check_daily`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return True (breached) if daily loss exceeds the hard limit.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.check_daily` · **Source:** [trading/risk/guardrails.py:128](../../../../trading/risk/guardrails.py#L128)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Acc used by the operation described above.
  ```

- **Returns:**

  ```text
  Whether check daily meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_daily_loss_breach`](../../../../tests/unit/trading/test_guardrails.py#L26)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_daily_loss_breach():
    g = FTMOGuardrails(daily_loss_limit=5000.0)
    acc = _make(daily_loss=5000.0)
    assert g.check_daily(acc)
    assert g.any_breach(acc)
    assert g.breach_reason(acc) == "daily_loss"
```

2. [test fixture: `test_percentage_daily_breach_moves_with_current_equity_but_max_loss_does_not`](../../../../tests/unit/trading/test_guardrails.py#L89)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_percentage_daily_breach_moves_with_current_equity_but_max_loss_does_not() -> None:
    g = FTMOGuardrails(limit_value_mode="percent_equity")
    acc = AccountState(initial_balance=100_000.0)
    acc.equity = 80_000.0
    acc.daily_loss = 4_000.0
    assert g.check_daily(acc)
    acc.daily_loss = 3_999.0
    assert not g.check_daily(acc)

    acc.equity = 91_000.0
    assert not g.check_max_drawdown(acc)
    acc.equity = 90_000.0
    assert g.check_max_drawdown(acc)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.check_max_drawdown`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return True if absolute loss from *initial* balance ≥ ``max_loss_limit``.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.check_max_drawdown` · **Source:** [trading/risk/guardrails.py:153](../../../../trading/risk/guardrails.py#L153)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Acc used by the operation described above.
  ```

- **Returns:**

  ```text
  Whether check max drawdown meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_max_drawdown_breach`](../../../../tests/unit/trading/test_guardrails.py#L35)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_max_drawdown_breach():
    g = FTMOGuardrails(max_loss_limit=10_000.0, trailing_dd_limit=0.0)
    acc = _make()
    acc.equity = 90_000.0  # $10k below initial — absolute max loss, not trailing
    assert g.check_max_drawdown(acc)
    assert g.breach_reason(acc) == "max_drawdown"
```

2. [test fixture: `test_max_loss_not_trailing_hwm`](../../../../tests/unit/trading/test_guardrails.py#L46)

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

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.check_soft_daily`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return True when the soft brick is active (no new entries).

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.check_soft_daily` · **Source:** [trading/risk/guardrails.py:139](../../../../trading/risk/guardrails.py#L139)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Acc used by the operation described above.
  ```

- **Returns:**

  ```text
  Whether check soft daily meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_soft_daily_does_not_hard_breach`](../../../../tests/unit/trading/test_guardrails.py#L118)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_soft_daily_does_not_hard_breach():
    g = FTMOGuardrails(daily_loss_limit=5000.0, soft_daily_loss_limit=2000.0)
    acc = _make(daily_loss=2500.0)
    assert g.check_soft_daily(acc)
    assert not g.check_daily(acc)
    assert not g.any_breach(acc)
    assert g.breach_reason(acc) is None
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.check_soft_trailing_dd`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return True when the trailing-DD soft brick is active.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.check_soft_trailing_dd` · **Source:** [trading/risk/guardrails.py:182](../../../../trading/risk/guardrails.py#L182)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Acc used by the operation described above.
  ```

- **Returns:**

  ```text
  Whether check soft trailing dd meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_soft_trailing_dd_does_not_hard_breach`](../../../../tests/unit/trading/test_guardrails.py#L147)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_soft_trailing_dd_does_not_hard_breach():
    g = FTMOGuardrails(trailing_dd_limit=0.07, soft_trailing_dd_limit=0.04)
    acc = AccountState(initial_balance=100_000.0)
    acc.update_equity(10_000.0)
    acc.balance = 105_500.0  # $4.5k off 110k peak: above $4k soft, under $7k hard
    acc.update_equity(0.0)
    assert g.check_soft_trailing_dd(acc)
    assert not g.check_trailing_dd(acc)
    assert not g.any_breach(acc)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.check_trade_risk`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return True (breached) if *risk* $ per trade exceeds the limit.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.check_trade_risk` · **Source:** [trading/risk/guardrails.py:197](../../../../trading/risk/guardrails.py#L197)

**Inputs and outputs:**

- **Args:**

  ```text
  risk: Numeric value used for the risk.
  acc: Acc used by the operation described above.
  ```

- **Returns:**

  ```text
  Whether check trade risk meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_trade_risk_check`](../../../../tests/unit/trading/test_guardrails.py#L54)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trade_risk_check():
    g = FTMOGuardrails(risk_per_trade_limit=1000.0)
    assert g.check_trade_risk(999.0) is False
    assert g.check_trade_risk(1001.0) is True
```

2. [test fixture: `test_percentage_limits_use_current_equity_and_initial_equity_as_selected`](../../../../tests/unit/trading/test_guardrails.py#L75)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert g.risk_per_trade_limit_for(acc) == 1_200.0
    assert g.daily_limit_for(acc) == 6_000.0
    assert g.soft_daily_limit_for(acc) == 6_000.0
    assert g.max_loss_limit_for(acc) == 10_000.0
    assert g.soft_max_loss_limit_for(acc) == 10_000.0
    assert not g.check_trade_risk(1_200.0, acc)
    assert g.check_trade_risk(1_200.01, acc)

    acc.equity = 80_000.0
    assert g.risk_per_trade_limit_for(acc) == 800.0
    assert g.daily_limit_for(acc) == 4_000.0
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.check_trailing_dd`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return True if enabled peak-to-trough DD reaches its initial-balance cap.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.check_trailing_dd` · **Source:** [trading/risk/guardrails.py:167](../../../../trading/risk/guardrails.py#L167)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Acc used by the operation described above.
  ```

- **Returns:**

  ```text
  Whether check trailing dd meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_trailing_dd_is_dollar_from_peak_not_pct_of_peak`](../../../../tests/unit/trading/test_guardrails.py#L131)

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

2. [test fixture: `test_soft_trailing_dd_does_not_hard_breach`](../../../../tests/unit/trading/test_guardrails.py#L148)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_soft_trailing_dd_does_not_hard_breach():
    g = FTMOGuardrails(trailing_dd_limit=0.07, soft_trailing_dd_limit=0.04)
    acc = AccountState(initial_balance=100_000.0)
    acc.update_equity(10_000.0)
    acc.balance = 105_500.0  # $4.5k off 110k peak: above $4k soft, under $7k hard
    acc.update_equity(0.0)
    assert g.check_soft_trailing_dd(acc)
    assert not g.check_trailing_dd(acc)
    assert not g.any_breach(acc)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.daily_limit_for`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Resolve the hard daily-loss threshold from the selected value mode.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.daily_limit_for` · **Source:** [trading/risk/guardrails.py:61](../../../../trading/risk/guardrails.py#L61)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Acc used by the operation described above.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``daily_limit_for``.
  ```

**Observed usage:**

1. [test fixture: `test_percentage_limits_use_current_equity_and_initial_equity_as_selected`](../../../../tests/unit/trading/test_guardrails.py#L71)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    acc = AccountState(initial_balance=100_000.0)
    acc.equity = 120_000.0

    assert g.risk_per_trade_limit_for(acc) == 1_200.0
    assert g.daily_limit_for(acc) == 6_000.0
    assert g.soft_daily_limit_for(acc) == 6_000.0
    assert g.max_loss_limit_for(acc) == 10_000.0
    assert g.soft_max_loss_limit_for(acc) == 10_000.0
    assert not g.check_trade_risk(1_200.0, acc)
    assert g.check_trade_risk(1_200.01, acc)
# … caller assertions omitted …
```

2. [production caller: `check_daily`](../../../../trading/risk/guardrails.py#L137)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def check_daily(self, acc: AccountState) -> bool:
    return acc.canonical_daily_loss() >= self.daily_limit_for(acc)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.max_loss_limit_for`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Resolve the maximum-loss threshold; percentage mode uses initial equity.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.max_loss_limit_for` · **Source:** [trading/risk/guardrails.py:87](../../../../trading/risk/guardrails.py#L87)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Acc used by the operation described above.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``max_loss_limit_for``.
  ```

**Observed usage:**

1. [test fixture: `test_percentage_limits_use_current_equity_and_initial_equity_as_selected`](../../../../tests/unit/trading/test_guardrails.py#L73)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    acc.equity = 120_000.0

    assert g.risk_per_trade_limit_for(acc) == 1_200.0
    assert g.daily_limit_for(acc) == 6_000.0
    assert g.soft_daily_limit_for(acc) == 6_000.0
    assert g.max_loss_limit_for(acc) == 10_000.0
    assert g.soft_max_loss_limit_for(acc) == 10_000.0
    assert not g.check_trade_risk(1_200.0, acc)
    assert g.check_trade_risk(1_200.01, acc)

    acc.equity = 80_000.0
# … caller assertions omitted …
```

2. [production caller: `check_max_drawdown`](../../../../trading/risk/guardrails.py#L165)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def check_max_drawdown(self, acc: AccountState) -> bool:
    return acc.loss_from_initial() >= self.max_loss_limit_for(acc)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.risk_per_trade_limit_for`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Resolve the hard per-trade threshold from current equity if selected.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.risk_per_trade_limit_for` · **Source:** [trading/risk/guardrails.py:115](../../../../trading/risk/guardrails.py#L115)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Acc used by the operation described above.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``risk_per_trade_limit_for``.
  ```

**Observed usage:**

1. [test fixture: `test_percentage_limits_use_current_equity_and_initial_equity_as_selected`](../../../../tests/unit/trading/test_guardrails.py#L70)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        soft_max_loss_limit_initial_pct=0.10,
    )
    acc = AccountState(initial_balance=100_000.0)
    acc.equity = 120_000.0

    assert g.risk_per_trade_limit_for(acc) == 1_200.0
    assert g.daily_limit_for(acc) == 6_000.0
    assert g.soft_daily_limit_for(acc) == 6_000.0
    assert g.max_loss_limit_for(acc) == 10_000.0
    assert g.soft_max_loss_limit_for(acc) == 10_000.0
    assert not g.check_trade_risk(1_200.0, acc)
# … caller assertions omitted …
```

2. [production caller: `check_trade_risk`](../../../../trading/risk/guardrails.py#L207)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def check_trade_risk(self, risk: float, acc: AccountState | None = None) -> bool:
    limit = self.risk_per_trade_limit if acc is None else self.risk_per_trade_limit_for(acc)
    return risk > limit
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.soft_daily_limit_for`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Resolve the soft daily threshold from current equity when requested.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.soft_daily_limit_for` · **Source:** [trading/risk/guardrails.py:74](../../../../trading/risk/guardrails.py#L74)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Acc used by the operation described above.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``soft_daily_limit_for``.
  ```

**Observed usage:**

1. [test fixture: `test_percentage_limits_use_current_equity_and_initial_equity_as_selected`](../../../../tests/unit/trading/test_guardrails.py#L72)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    acc = AccountState(initial_balance=100_000.0)
    acc.equity = 120_000.0

    assert g.risk_per_trade_limit_for(acc) == 1_200.0
    assert g.daily_limit_for(acc) == 6_000.0
    assert g.soft_daily_limit_for(acc) == 6_000.0
    assert g.max_loss_limit_for(acc) == 10_000.0
    assert g.soft_max_loss_limit_for(acc) == 10_000.0
    assert not g.check_trade_risk(1_200.0, acc)
    assert g.check_trade_risk(1_200.01, acc)

# … caller assertions omitted …
```

2. [production caller: `check_soft_daily`](../../../../trading/risk/guardrails.py#L148)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def check_soft_daily(self, acc: AccountState) -> bool:
    soft = self.soft_daily_limit_for(acc)
    if soft <= 0.0:
        return False
    return acc.canonical_daily_loss() >= soft
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.soft_max_loss_limit_for`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Resolve the soft maximum-loss threshold from initial equity.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.soft_max_loss_limit_for` · **Source:** [trading/risk/guardrails.py:100](../../../../trading/risk/guardrails.py#L100)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Acc used by the operation described above.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``soft_max_loss_limit_for``.
  ```

**Observed usage:**

1. [test fixture: `test_percentage_limits_use_current_equity_and_initial_equity_as_selected`](../../../../tests/unit/trading/test_guardrails.py#L74)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    assert g.risk_per_trade_limit_for(acc) == 1_200.0
    assert g.daily_limit_for(acc) == 6_000.0
    assert g.soft_daily_limit_for(acc) == 6_000.0
    assert g.max_loss_limit_for(acc) == 10_000.0
    assert g.soft_max_loss_limit_for(acc) == 10_000.0
    assert not g.check_trade_risk(1_200.0, acc)
    assert g.check_trade_risk(1_200.01, acc)

    acc.equity = 80_000.0
    assert g.risk_per_trade_limit_for(acc) == 800.0
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
