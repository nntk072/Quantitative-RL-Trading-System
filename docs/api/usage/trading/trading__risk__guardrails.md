# Trading · `risk.guardrails`

This page contains 18 public callable records owned by `trading.risk.guardrails`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `FTMOGuardrails`

**Kind:** class · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Training-compatible account guardrails for daily and total loss limits.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails` · **Source:** [trading/risk/guardrails.py:83](../../../../trading/risk/guardrails.py#L83)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `_env_stub`](../../../../tests/unit/simulation/test_environment/test_fixed_risk_sizing.py#L57)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    stub.contract_size = kw.get("contract_size", 1.0)
    stub.min_lot = kw.get("min_lot", 0.01)
    stub.max_lot = kw.get("max_lot", 100.0)
    stub.lot_step = kw.get("lot_step", 0.000001)
    stub.max_loss_per_trade_usd = kw.get("max_loss_per_trade_usd", 900.0)
    stub.guardrails = kw.get("guardrails", FTMOGuardrails())
    stub.cost_model = kw.get("cost_model", CostModel())
    for name in (
        "_sizing_equity",
        "_risk_budget_usd",
        "_risk_band_action_unit",
# … caller assertions omitted …
```

2. [test fixture: `test_fixed_mode_ignores_equity_drift`](../../../../tests/unit/simulation/test_environment/test_fixed_risk_sizing.py#L160)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fixed_mode_ignores_equity_drift() -> None:
    entry, stop = 25_000.0, 80.0
    sizes = set()
    for equity in (25_000.0, 100_000.0, 500_000.0):
        env = _env_stub(
            "fixed",
            500.0,
            equity=equity,
            guardrails=FTMOGuardrails(limit_value_mode="fixed_usd"),
        )
        lots = env._compute_lots_for(0.0, entry, entry - stop)
        sizes.add(round(lots * stop, 6))
    assert sizes == {500.0}
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `adverse_position_loss_limit_usd`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Resolve the adverse-excursion cutoff without placing it inside planned risk.

**Exact API:** {py:obj}`trading.risk.guardrails.adverse_position_loss_limit_usd` · **Source:** [trading/risk/guardrails.py:49](../../../../trading/risk/guardrails.py#L49)

**Inputs and outputs:**

- **Args:**

  ```text
  configured_limit_usd: Configured dollar floor for adverse excursion.
  planned_risk_usd: Entry risk at the structural stop, if known.
  respect_planned_risk: Whether the cutoff must include planned risk.
  planned_risk_multiplier: Multiplier applied to planned risk.
  ```

- **Returns:**

  ```text
  The adverse-excursion cutoff in account currency.
  ```

- **Raises:**

  ```text
  ValueError: If a limit or multiplier is non-finite or negative.
  ```

**Observed usage:**

1. [test fixture: `test_shared_adverse_position_loss_limit`](../../../../tests/unit/trading/test_guardrails.py#L68)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    respect: bool,
    multiplier: float,
    expected: float,
) -> None:
    assert (
        adverse_position_loss_limit_usd(
            configured,
            planned,
            respect_planned_risk=respect,
            planned_risk_multiplier=multiplier,
        )
        == expected
    )
```

2. [test fixture: `test_adverse_position_loss_limit_rejects_non_finite_values`](../../../../tests/unit/trading/test_guardrails.py#L80)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_adverse_position_loss_limit_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        adverse_position_loss_limit_usd(
            float("inf"),
            0.0,
            respect_planned_risk=True,
            planned_risk_multiplier=1.0,
        )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `guardrail_breach_scope`

**Kind:** function · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return the lifecycle scope for a hard account-guardrail breach.

**Exact API:** {py:obj}`trading.risk.guardrails.guardrail_breach_scope` · **Source:** [trading/risk/guardrails.py:25](../../../../trading/risk/guardrails.py#L25)

**Inputs and outputs:**

- **Args:**

  ```text
  reason: Stable reason returned by ``FTMOGuardrails.breach_reason``.
  ```

- **Returns:**

  ```text
  ``"rollout"`` for a hard loss breach, or ``None`` when no breach
  occurred.
  ```

- **Raises:**

  ```text
  ValueError: If a non-null reason is not a recognized hard breach.
  ```

**Observed usage:**

1. [test fixture: `test_guardrail_breach_scope_is_shared_and_explicit`](../../../../tests/unit/trading/test_guardrails.py#L44)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_guardrail_breach_scope_is_shared_and_explicit(
    reason: str | None,
    expected_scope: str | None,
) -> None:
    assert guardrail_breach_scope(reason) == expected_scope
```

2. [test fixture: `test_guardrail_breach_scope_rejects_unknown_reason`](../../../../tests/unit/trading/test_guardrails.py#L49)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_guardrail_breach_scope_rejects_unknown_reason() -> None:
    with pytest.raises(ValueError, match="unsupported hard guardrail"):
        guardrail_breach_scope("unknown")
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.any_breach`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return whether any configured account guardrail is breached.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.any_breach` · **Source:** [trading/risk/guardrails.py:316](../../../../trading/risk/guardrails.py#L316)

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

1. [test fixture: `test_no_breach`](../../../../tests/unit/trading/test_guardrails.py#L27)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_no_breach():
    g = FTMOGuardrails()
    acc = _make(daily_loss=1000.0, max_dd=500.0)
    assert not g.any_breach(acc)
    assert g.breach_reason(acc) is None
```

2. [test fixture: `test_daily_loss_equality_is_allowed_and_breach_occurs_below_floor`](../../../../tests/unit/trading/test_guardrails.py#L96)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_daily_loss_equality_is_allowed_and_breach_occurs_below_floor():
    g = FTMOGuardrails()
    acc = _make(daily_loss=5000.0)
    assert not g.check_daily(acc)
    acc.daily_loss = 5_000.01
    acc.equity = acc.session_start_equity - 5_000.01
    acc.balance = acc.equity
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

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.breach_reason` · **Source:** [trading/risk/guardrails.py:327](../../../../trading/risk/guardrails.py#L327)

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

1. [test fixture: `test_no_breach`](../../../../tests/unit/trading/test_guardrails.py#L28)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_no_breach():
    g = FTMOGuardrails()
    acc = _make(daily_loss=1000.0, max_dd=500.0)
    assert not g.any_breach(acc)
    assert g.breach_reason(acc) is None
```

2. [test fixture: `test_daily_loss_equality_is_allowed_and_breach_occurs_below_floor`](../../../../tests/unit/trading/test_guardrails.py#L97)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_daily_loss_equality_is_allowed_and_breach_occurs_below_floor():
    g = FTMOGuardrails()
    acc = _make(daily_loss=5000.0)
    assert not g.check_daily(acc)
    acc.daily_loss = 5_000.01
    acc.equity = acc.session_start_equity - 5_000.01
    acc.balance = acc.equity
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

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.check_daily` · **Source:** [trading/risk/guardrails.py:229](../../../../trading/risk/guardrails.py#L229)

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

1. [test fixture: `test_daily_loss_equality_is_allowed_and_breach_occurs_below_floor`](../../../../tests/unit/trading/test_guardrails.py#L91)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_daily_loss_equality_is_allowed_and_breach_occurs_below_floor():
    g = FTMOGuardrails()
    acc = _make(daily_loss=5000.0)
    assert not g.check_daily(acc)
    acc.daily_loss = 5_000.01
    acc.equity = acc.session_start_equity - 5_000.01
    acc.balance = acc.equity
    assert g.check_daily(acc)
    assert g.any_breach(acc)
    assert g.breach_reason(acc) == "daily_loss"
```

2. [test fixture: `test_daily_percentage_allowance_stays_fixed_for_all_max_drawdown_modes`](../../../../tests/unit/trading/test_guardrails.py#L221)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    g = FTMOGuardrails(limit_value_mode="percent_equity", max_drawdown_mode=mode)  # type: ignore[arg-type]
    acc = AccountState(initial_balance=100_000.0)
    acc.equity = 95_000.0
    acc.balance = acc.equity
    acc.daily_loss = 5_000.0
    assert not g.check_daily(acc)
    acc.balance = acc.equity = 94_999.99
    acc.daily_loss = 5_000.01
    assert g.check_daily(acc)
    acc.balance = acc.equity = 95_001.0
    acc.daily_loss = 4_999.0
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.check_max_drawdown`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return True when equity breaches the configured maximum-loss floor.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.check_max_drawdown` · **Source:** [trading/risk/guardrails.py:256](../../../../trading/risk/guardrails.py#L256)

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

1. [test fixture: `test_max_drawdown_breach`](../../../../tests/unit/trading/test_guardrails.py#L104)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_max_drawdown_breach():
    g = FTMOGuardrails(max_loss_limit=10_000.0, trailing_dd_limit=0.0)
    acc = _make()
    acc.equity = 90_000.0  # Equality at the static floor remains allowed.
    assert not g.check_max_drawdown(acc)
    acc.equity = 89_999.99  # Static max loss fails only below its floor.
    assert g.check_max_drawdown(acc)
    assert g.breach_reason(acc) == "max_drawdown"
```

2. [test fixture: `test_max_loss_not_trailing_hwm`](../../../../tests/unit/trading/test_guardrails.py#L117)

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

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.check_soft_daily`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return True when the soft brick is active (no new entries).

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.check_soft_daily` · **Source:** [trading/risk/guardrails.py:241](../../../../trading/risk/guardrails.py#L241)

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

1. [test fixture: `test_soft_daily_does_not_hard_breach`](../../../../tests/unit/trading/test_guardrails.py#L352)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_soft_daily_does_not_hard_breach():
    g = FTMOGuardrails(
        limit_value_mode="fixed_usd",
        daily_loss_limit_pct=0.05,
        soft_daily_loss_limit_pct=0.02,
    )
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

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.check_soft_trailing_dd` · **Source:** [trading/risk/guardrails.py:286](../../../../trading/risk/guardrails.py#L286)

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

1. [test fixture: `test_soft_trailing_dd_does_not_hard_breach`](../../../../tests/unit/trading/test_guardrails.py#L381)

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

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.check_trade_risk` · **Source:** [trading/risk/guardrails.py:301](../../../../trading/risk/guardrails.py#L301)

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

1. [test fixture: `test_trade_risk_check`](../../../../tests/unit/trading/test_guardrails.py#L164)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trade_risk_check():
    g = FTMOGuardrails(risk_per_trade_limit=1000.0)
    assert g.check_trade_risk(999.0) is False
    assert g.check_trade_risk(1_000.0 + 5e-10) is False
    assert g.check_trade_risk(1001.0) is True
```

2. [test fixture: `test_percentage_limits_use_initial_equity_for_daily_and_max_loss`](../../../../tests/unit/trading/test_guardrails.py#L186)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert g.risk_per_trade_limit_for(acc) == 1_200.0
    assert g.daily_limit_for(acc) == 5_000.0
    assert g.soft_daily_limit_for(acc) == 5_000.0
    assert g.max_loss_limit_for(acc) == 10_000.0
    assert g.soft_max_loss_limit_for(acc) == 10_000.0
    assert not g.check_trade_risk(1_200.0, acc)
    assert g.check_trade_risk(1_200.01, acc)

    acc.equity = 80_000.0
    assert g.risk_per_trade_limit_for(acc) == 800.0
    assert g.daily_limit_for(acc) == 5_000.0
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.check_trailing_dd`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return True if enabled peak-to-trough DD reaches its initial-balance cap.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.check_trailing_dd` · **Source:** [trading/risk/guardrails.py:271](../../../../trading/risk/guardrails.py#L271)

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

1. [test fixture: `test_trailing_dd_is_dollar_from_peak_not_pct_of_peak`](../../../../tests/unit/trading/test_guardrails.py#L365)

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

2. [test fixture: `test_soft_trailing_dd_does_not_hard_breach`](../../../../tests/unit/trading/test_guardrails.py#L382)

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

**Purpose:** Derive the hard daily-loss threshold from initial equity only.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.daily_limit_for` · **Source:** [trading/risk/guardrails.py:130](../../../../trading/risk/guardrails.py#L130)

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

1. [test fixture: `test_percentage_limits_use_initial_equity_for_daily_and_max_loss`](../../../../tests/unit/trading/test_guardrails.py#L182)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    acc = AccountState(initial_balance=100_000.0)
    acc.equity = 120_000.0

    assert g.risk_per_trade_limit_for(acc) == 1_200.0
    assert g.daily_limit_for(acc) == 5_000.0
    assert g.soft_daily_limit_for(acc) == 5_000.0
    assert g.max_loss_limit_for(acc) == 10_000.0
    assert g.soft_max_loss_limit_for(acc) == 10_000.0
    assert not g.check_trade_risk(1_200.0, acc)
    assert g.check_trade_risk(1_200.01, acc)
# … caller assertions omitted …
```

2. [test fixture: `test_daily_loss_threshold_uses_percentage_even_in_fixed_other_limits_mode`](../../../../tests/unit/trading/test_guardrails.py#L207)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    account = AccountState(initial_balance=100_000.0, policy_mode="repeated_payout")
    account.balance = account.equity = 102_000.0
    account.session_start_balance = account.session_start_equity = 102_000.0

    assert guardrails.daily_limit_for(account) == pytest.approx(5_000.0)
    assert guardrails.soft_daily_limit_for(account) == pytest.approx(2_000.0)
    assert account.daily_floor(guardrails.daily_limit_for(account)) == pytest.approx(97_000.0)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.max_drawdown_from_reference`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return current loss from the reference equity for the selected mode.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.max_drawdown_from_reference` · **Source:** [trading/risk/guardrails.py:188](../../../../trading/risk/guardrails.py#L188)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Account state containing current and reference equity values.
  ```

- **Returns:**

  ```text
  Nonnegative drawdown amount from the mode-specific reference.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = FTMOGuardrails(...)
result = instance.max_drawdown_from_reference(acc=...)
```

**Lifecycle context:** This callable participates in `FTMOGuardrails`: Training-compatible account guardrails for daily and total loss limits. Related public lifecycle methods: {py:obj}`trading.risk.guardrails.FTMOGuardrails.daily_limit_for`, {py:obj}`trading.risk.guardrails.FTMOGuardrails.soft_daily_limit_for`, {py:obj}`trading.risk.guardrails.FTMOGuardrails.max_loss_limit_for`, {py:obj}`trading.risk.guardrails.FTMOGuardrails.max_loss_floor_for`, {py:obj}`trading.risk.guardrails.FTMOGuardrails.max_drawdown_from_reference`, {py:obj}`trading.risk.guardrails.FTMOGuardrails.soft_max_loss_limit_for`, {py:obj}`trading.risk.guardrails.FTMOGuardrails.risk_per_trade_limit_for`, {py:obj}`trading.risk.guardrails.FTMOGuardrails.check_daily`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.max_loss_floor_for`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Return the active maximum-loss floor, capped at initial equity.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.max_loss_floor_for` · **Source:** [trading/risk/guardrails.py:163](../../../../trading/risk/guardrails.py#L163)

**Inputs and outputs:**

- **Args:**

  ```text
  acc: Account state containing initial and reference equity values.
  ```

- **Returns:**

  ```text
  Active maximum-loss equity floor, capped at initial balance.
  ```

**Observed usage:**

1. [test fixture: `test_max_loss_floor_modes_share_initial_allowance_and_cap_at_initial`](../../../../tests/unit/trading/test_guardrails.py#L158)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    account = AccountState(initial_balance=100_000.0)
    account.peak_equity = peak
    account.peak_eod_equity = peak
    account.equity = equity

    assert guardrails.max_loss_floor_for(account) == expected_floor
    assert guardrails.check_max_drawdown(account) is breached
```

2. [test fixture: `test_payout_reanchors_daily_loss_and_locks_trailing_floor_at_initial`](../../../../tests/unit/trading/test_guardrails.py#L304)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        assert guardrails.check_max_drawdown(account)
    account.update_equity(-5_000.0)
    assert not guardrails.check_daily(account)
    account.update_equity(-5_000.01)
    assert guardrails.check_daily(account)
    assert guardrails.max_loss_floor_for(account) == expected_max_floor
    account.equity = expected_max_floor
    assert not guardrails.check_max_drawdown(account)
    account.equity = expected_max_floor - 0.01
    assert guardrails.check_max_drawdown(account)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.max_loss_limit_for`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Derive the maximum-loss allowance from initial equity only.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.max_loss_limit_for` · **Source:** [trading/risk/guardrails.py:152](../../../../trading/risk/guardrails.py#L152)

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

1. [test fixture: `test_percentage_limits_use_initial_equity_for_daily_and_max_loss`](../../../../tests/unit/trading/test_guardrails.py#L184)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    acc.equity = 120_000.0

    assert g.risk_per_trade_limit_for(acc) == 1_200.0
    assert g.daily_limit_for(acc) == 5_000.0
    assert g.soft_daily_limit_for(acc) == 5_000.0
    assert g.max_loss_limit_for(acc) == 10_000.0
    assert g.soft_max_loss_limit_for(acc) == 10_000.0
    assert not g.check_trade_risk(1_200.0, acc)
    assert g.check_trade_risk(1_200.01, acc)

    acc.equity = 80_000.0
# … caller assertions omitted …
```

2. [production caller: `max_loss_floor_for`](../../../../trading/risk/guardrails.py#L178)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def max_loss_floor_for(self, acc: AccountState) -> float:
    initial = float(acc.initial_balance)
    allowance = self.max_loss_limit_for(acc)
    floor = initial - allowance
    if self.max_drawdown_mode == "eod":
        floor = max(floor, float(acc.peak_eod_equity) - allowance)
    elif self.max_drawdown_mode == "intraday_trailing":
        floor = max(floor, float(acc.peak_equity) - allowance)
    if self.max_drawdown_mode != "static" and acc.payout_drawdown_floor is not None:
        floor = max(floor, float(acc.payout_drawdown_floor))
    return min(initial, floor)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.risk_per_trade_limit_for`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Resolve the hard per-trade threshold from current equity if selected.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.risk_per_trade_limit_for` · **Source:** [trading/risk/guardrails.py:216](../../../../trading/risk/guardrails.py#L216)

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

1. [test fixture: `test_percentage_limits_use_initial_equity_for_daily_and_max_loss`](../../../../tests/unit/trading/test_guardrails.py#L181)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        soft_max_loss_limit_initial_pct=0.10,
    )
    acc = AccountState(initial_balance=100_000.0)
    acc.equity = 120_000.0

    assert g.risk_per_trade_limit_for(acc) == 1_200.0
    assert g.daily_limit_for(acc) == 5_000.0
    assert g.soft_daily_limit_for(acc) == 5_000.0
    assert g.max_loss_limit_for(acc) == 10_000.0
    assert g.soft_max_loss_limit_for(acc) == 10_000.0
    assert not g.check_trade_risk(1_200.0, acc)
# … caller assertions omitted …
```

2. [production caller: `check_trade_risk`](../../../../trading/risk/guardrails.py#L311)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def check_trade_risk(self, risk: float, acc: AccountState | None = None) -> bool:
    limit = self.risk_per_trade_limit if acc is None else self.risk_per_trade_limit_for(acc)
    # Allow equality, including the final floating-point ulp introduced by
    # converting an affordable stepped lot count back into dollar risk.
    return float(risk) > float(limit) + 1e-9
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.soft_daily_limit_for`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Derive the soft daily threshold from initial equity only.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.soft_daily_limit_for` · **Source:** [trading/risk/guardrails.py:141](../../../../trading/risk/guardrails.py#L141)

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

1. [test fixture: `test_percentage_limits_use_initial_equity_for_daily_and_max_loss`](../../../../tests/unit/trading/test_guardrails.py#L183)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    acc = AccountState(initial_balance=100_000.0)
    acc.equity = 120_000.0

    assert g.risk_per_trade_limit_for(acc) == 1_200.0
    assert g.daily_limit_for(acc) == 5_000.0
    assert g.soft_daily_limit_for(acc) == 5_000.0
    assert g.max_loss_limit_for(acc) == 10_000.0
    assert g.soft_max_loss_limit_for(acc) == 10_000.0
    assert not g.check_trade_risk(1_200.0, acc)
    assert g.check_trade_risk(1_200.01, acc)

# … caller assertions omitted …
```

2. [test fixture: `test_daily_loss_threshold_uses_percentage_even_in_fixed_other_limits_mode`](../../../../tests/unit/trading/test_guardrails.py#L208)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    account = AccountState(initial_balance=100_000.0, policy_mode="repeated_payout")
    account.balance = account.equity = 102_000.0
    account.session_start_balance = account.session_start_equity = 102_000.0

    assert guardrails.daily_limit_for(account) == pytest.approx(5_000.0)
    assert guardrails.soft_daily_limit_for(account) == pytest.approx(2_000.0)
    assert account.daily_floor(guardrails.daily_limit_for(account)) == pytest.approx(97_000.0)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `FTMOGuardrails.soft_max_loss_limit_for`

**Kind:** method · **Status:** stable · **Owner:** `trading.risk.guardrails`

**Purpose:** Derive the soft maximum-loss threshold from initial equity only.

**Exact API:** {py:obj}`trading.risk.guardrails.FTMOGuardrails.soft_max_loss_limit_for` · **Source:** [trading/risk/guardrails.py:205](../../../../trading/risk/guardrails.py#L205)

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

1. [test fixture: `test_percentage_limits_use_initial_equity_for_daily_and_max_loss`](../../../../tests/unit/trading/test_guardrails.py#L185)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    assert g.risk_per_trade_limit_for(acc) == 1_200.0
    assert g.daily_limit_for(acc) == 5_000.0
    assert g.soft_daily_limit_for(acc) == 5_000.0
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
