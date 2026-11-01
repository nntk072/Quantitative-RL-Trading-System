# Trading · `policy.config`

This page contains 8 public callable records owned by `trading.policy.config`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TradingPolicyConfig`

**Kind:** class · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Resolved account and payout policy settings used by simulation and live strategies.

**Exact API:** {py:obj}`trading.policy.config.TradingPolicyConfig` · **Source:** [trading/policy/config.py:24](../../../../trading/policy/config.py#L24)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `_repeated_env_stub`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L77)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _repeated_env_stub(*, reserve: float = 0.0, episodic: bool = False) -> TradingEnv:
    env = TradingEnv.__new__(TradingEnv)
    env.risk_mode = "dynamic"
    env.fixed_risk_usd = 0.0
    env.repeated_payout_policy = True
    env.trading_policy = TradingPolicyConfig(
        mode="repeated_payout",
        execution_reserve_usd=reserve,
    ).validate()
    env.guardrails = FTMOGuardrails(
        daily_loss_limit=5_000.0,
        max_loss_limit=10_000.0,
        risk_per_trade_limit=900.0,
        trailing_dd_limit=0.0,
# … caller assertions omitted …
```

2. [production caller: `resolve_trading_policy`](../../../../trading/policy/config.py#L116)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        block = {}
    mode = str(block.get("mode", "legacy")).strip().lower()
    repeated = block.get("repeated_payout", {}) or {}
    account = cfg.get("account", {}) if hasattr(cfg, "get") else {}
    initial = float(account.get("initial_balance", 100_000.0))
    result = TradingPolicyConfig(
        mode=mode,
        operating_balance=float(repeated.get("operating_balance", initial)),
        profit_target_balance=float(
            repeated.get("payout_target_balance", repeated.get("profit_target_balance", 110_000.0))
        ),
        account_floor=float(
            repeated.get("account_floor_equity", repeated.get("account_floor", 90_000.0))
        ),
        daily_loss_limit=float(repeated.get("daily_loss_limit", 5_000.0)),
        min_agent_risk_frac=_float_or_default(
            repeated.get("min_agent_risk_frac")
            if repeated.get("min_agent_risk_frac") is not None
            else repeated.get("agent_risk_min_frac"),
            0.0,
        ),
        max_agent_risk_frac=_float_or_default(
            repeated.get("max_agent_risk_frac")
            if repeated.get("max_agent_risk_frac") is not None
            else repeated.get("agent_risk_max_frac"),
            0.009,
        ),
        execution_reserve_usd=_float_or_default(
            repeated.get("execution_reserve_usd")
            if repeated.get("execution_reserve_usd") is not None
            else repeated.get("reserve_cost_buffer_usd"),
            0.0,
        ),
        payout_trigger=str(repeated.get("payout_trigger", "realized_balance_flat")),
        continue_after_payout=bool(repeated.get("continue_after_payout", True)),
        trailing_dd_limit=float(repeated.get("trailing_dd_limit", 0.0)),
        enforce_remaining_daily_capacity=bool(
            repeated.get("enforce_remaining_daily_capacity", True)
        ),
        enforce_remaining_account_capacity=bool(
            repeated.get("enforce_remaining_account_capacity", True)
        ),
        repeated_eval=bool(repeated.get("repeated_eval", True)),
    )
    return result.validate()
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `resolve_trading_policy`

**Kind:** function · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Resolve trading policy settings from an attribute-based configuration.

**Exact API:** {py:obj}`trading.policy.config.resolve_trading_policy` · **Source:** [trading/policy/config.py:100](../../../../trading/policy/config.py#L100)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Configuration object containing the optional trading policy block.
  ```

- **Returns:**

  ```text
  Validated policy settings with defaults applied.
  ```

**Observed usage:**

1. [test fixture: `test_repeated_policy_config_resolves_without_changing_default`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L15)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_repeated_policy_config_resolves_without_changing_default() -> None:
    legacy = resolve_trading_policy(load_config())
    assert legacy.mode == "legacy"
    repeated = resolve_trading_policy(load_config(["trading_policy.mode=repeated_payout"]))
    assert repeated.operating_balance == 100_000.0
    assert repeated.profit_target_balance == 110_000.0
    assert repeated.account_floor == 90_000.0
    assert repeated.max_agent_risk_frac == pytest.approx(0.009)
```

2. [test fixture: `test_repeated_policy_rejects_one_percent_risk`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L69)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_repeated_policy_rejects_one_percent_risk() -> None:
    with pytest.raises(ValueError, match="max agent risk"):
        load = load_config(
            [
                "trading_policy.mode=repeated_payout",
                "trading_policy.repeated_payout.max_agent_risk_frac=0.01",
            ]
        )
        resolve_trading_policy(load)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingPolicyConfig`

**Kind:** class · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Resolved account and payout policy settings used by simulation and live strategies.

**Exact API:** {py:obj}`trading.policy.config.TradingPolicyConfig` · **Source:** [trading/policy/config.py:24](../../../../trading/policy/config.py#L24)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `_repeated_env_stub`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L77)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _repeated_env_stub(*, reserve: float = 0.0, episodic: bool = False) -> TradingEnv:
    env = TradingEnv.__new__(TradingEnv)
    env.risk_mode = "dynamic"
    env.fixed_risk_usd = 0.0
    env.repeated_payout_policy = True
    env.trading_policy = TradingPolicyConfig(
        mode="repeated_payout",
        execution_reserve_usd=reserve,
    ).validate()
    env.guardrails = FTMOGuardrails(
        daily_loss_limit=5_000.0,
        max_loss_limit=10_000.0,
        risk_per_trade_limit=900.0,
        trailing_dd_limit=0.0,
# … caller assertions omitted …
```

2. [production caller: `resolve_trading_policy`](../../../../trading/policy/config.py#L116)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        block = {}
    mode = str(block.get("mode", "legacy")).strip().lower()
    repeated = block.get("repeated_payout", {}) or {}
    account = cfg.get("account", {}) if hasattr(cfg, "get") else {}
    initial = float(account.get("initial_balance", 100_000.0))
    result = TradingPolicyConfig(
        mode=mode,
        operating_balance=float(repeated.get("operating_balance", initial)),
        profit_target_balance=float(
            repeated.get("payout_target_balance", repeated.get("profit_target_balance", 110_000.0))
        ),
        account_floor=float(
            repeated.get("account_floor_equity", repeated.get("account_floor", 90_000.0))
        ),
        daily_loss_limit=float(repeated.get("daily_loss_limit", 5_000.0)),
        min_agent_risk_frac=_float_or_default(
            repeated.get("min_agent_risk_frac")
            if repeated.get("min_agent_risk_frac") is not None
            else repeated.get("agent_risk_min_frac"),
            0.0,
        ),
        max_agent_risk_frac=_float_or_default(
            repeated.get("max_agent_risk_frac")
            if repeated.get("max_agent_risk_frac") is not None
            else repeated.get("agent_risk_max_frac"),
            0.009,
        ),
        execution_reserve_usd=_float_or_default(
            repeated.get("execution_reserve_usd")
            if repeated.get("execution_reserve_usd") is not None
            else repeated.get("reserve_cost_buffer_usd"),
            0.0,
        ),
        payout_trigger=str(repeated.get("payout_trigger", "realized_balance_flat")),
        continue_after_payout=bool(repeated.get("continue_after_payout", True)),
        trailing_dd_limit=float(repeated.get("trailing_dd_limit", 0.0)),
        enforce_remaining_daily_capacity=bool(
            repeated.get("enforce_remaining_daily_capacity", True)
        ),
        enforce_remaining_account_capacity=bool(
            repeated.get("enforce_remaining_account_capacity", True)
        ),
        repeated_eval=bool(repeated.get("repeated_eval", True)),
    )
    return result.validate()
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `resolve_trading_policy`

**Kind:** function · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Resolve trading policy settings from an attribute-based configuration.

**Exact API:** {py:obj}`trading.policy.config.resolve_trading_policy` · **Source:** [trading/policy/config.py:100](../../../../trading/policy/config.py#L100)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Configuration object containing the optional trading policy block.
  ```

- **Returns:**

  ```text
  Validated policy settings with defaults applied.
  ```

**Observed usage:**

1. [test fixture: `test_repeated_policy_config_resolves_without_changing_default`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L15)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_repeated_policy_config_resolves_without_changing_default() -> None:
    legacy = resolve_trading_policy(load_config())
    assert legacy.mode == "legacy"
    repeated = resolve_trading_policy(load_config(["trading_policy.mode=repeated_payout"]))
    assert repeated.operating_balance == 100_000.0
    assert repeated.profit_target_balance == 110_000.0
    assert repeated.account_floor == 90_000.0
    assert repeated.max_agent_risk_frac == pytest.approx(0.009)
```

2. [test fixture: `test_repeated_policy_rejects_one_percent_risk`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L69)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_repeated_policy_rejects_one_percent_risk() -> None:
    with pytest.raises(ValueError, match="max agent risk"):
        load = load_config(
            [
                "trading_policy.mode=repeated_payout",
                "trading_policy.repeated_payout.max_agent_risk_frac=0.01",
            ]
        )
        resolve_trading_policy(load)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `resolve_trading_policy_mapping`

**Kind:** function · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Resolve trading policy settings from a mapping configuration.

**Exact API:** {py:obj}`trading.policy.config.resolve_trading_policy_mapping` · **Source:** [trading/policy/config.py:158](../../../../trading/policy/config.py#L158)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Configuration mapping containing the optional trading policy block.
  ```

- **Returns:**

  ```text
  Validated policy settings with defaults applied.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = resolve_trading_policy_mapping(cfg=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingPolicyConfig.repeated_payout`

**Kind:** method · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Return whether the account policy enables repeated payouts.

**Exact API:** {py:obj}`trading.policy.config.TradingPolicyConfig.repeated_payout` · **Source:** [trading/policy/config.py:50](../../../../trading/policy/config.py#L50)

**Inputs and outputs:**

- **Returns:**

  ```text
  Whether repeated payout meets the requested condition.
  ```

**Observed usage:**

1. [production caller: `validate`](../../../../trading/policy/config.py#L66)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
        if self.mode not in {"legacy", "repeated_payout"}:
            raise ValueError(f"unknown trading_policy.mode: {self.mode!r}")
        if self.repeated_payout:
            if self.profit_target_balance <= self.operating_balance:
                raise ValueError("repeated payout target must exceed operating balance")
            if self.account_floor >= self.operating_balance:
                raise ValueError("repeated payout account floor must be below operating balance")
            if self.daily_loss_limit < 0.0:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingPolicyConfig.to_dict`

**Kind:** method · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Return the policy settings as a JSON-compatible mapping.

**Exact API:** {py:obj}`trading.policy.config.TradingPolicyConfig.to_dict` · **Source:** [trading/policy/config.py:91](../../../../trading/policy/config.py#L91)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TradingPolicyConfig(...)
result = instance.to_dict()
```

**Lifecycle context:** This callable participates in `TradingPolicyConfig`: Resolved account and payout policy settings used by simulation and live strategies. Related public lifecycle methods: {py:obj}`trading.policy.config.TradingPolicyConfig.repeated_payout`, {py:obj}`trading.policy.config.TradingPolicyConfig.validate`, {py:obj}`trading.policy.config.TradingPolicyConfig.to_dict`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingPolicyConfig.validate`

**Kind:** method · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Validate payout thresholds and account-floor relationships.

**Exact API:** {py:obj}`trading.policy.config.TradingPolicyConfig.validate` · **Source:** [trading/policy/config.py:58](../../../../trading/policy/config.py#L58)

**Inputs and outputs:**

- **Returns:**

  ```text
  Result of validate payout thresholds and account-floor relationships.
  ```

**Observed usage:**

1. [test fixture: `_repeated_env_stub`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L77)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _repeated_env_stub(*, reserve: float = 0.0, episodic: bool = False) -> TradingEnv:
    env = TradingEnv.__new__(TradingEnv)
    env.risk_mode = "dynamic"
    env.fixed_risk_usd = 0.0
    env.repeated_payout_policy = True
    env.trading_policy = TradingPolicyConfig(
        mode="repeated_payout",
        execution_reserve_usd=reserve,
    ).validate()
    env.guardrails = FTMOGuardrails(
        daily_loss_limit=5_000.0,
        max_loss_limit=10_000.0,
        risk_per_trade_limit=900.0,
        trailing_dd_limit=0.0,
# … caller assertions omitted …
```

2. [production caller: `resolve_trading_policy`](../../../../trading/policy/config.py#L155)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        enforce_remaining_account_capacity=bool(
            repeated.get("enforce_remaining_account_capacity", True)
        ),
        repeated_eval=bool(repeated.get("repeated_eval", True)),
    )
    return result.validate()
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
