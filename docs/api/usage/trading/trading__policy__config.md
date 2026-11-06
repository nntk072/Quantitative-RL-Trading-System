# Trading · `policy.config`

This page contains 10 public callable records owned by `trading.policy.config`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TradingPolicyConfig`

**Kind:** class · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Resolved account and payout policy settings used by simulation and live strategies.

**Exact API:** {py:obj}`trading.policy.config.TradingPolicyConfig` · **Source:** [trading/policy/config.py:24](../../../../trading/policy/config.py#L24)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `test_repeated_payout_backtest_withdraws_realized_overshoot_and_reports_economic_value`](../../../../tests/integration/backtest/test_repeated_payout_backtest.py#L39)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "last_swing_high": np.full(len(index), 103.0),
        },
        index=index,
    )
    actions = iter([1, 2, 2, 2, 2, 2])
    policy = TradingPolicyConfig(
        mode="repeated_payout",
        operating_balance=100.0,
        profit_target_balance=101.5,
        account_floor=90.0,
        daily_loss_limit_pct=0.20,
        max_agent_risk_frac=0.009,
    ).validate()
    if policy_input == "instance":
        policy_config: TradingPolicyConfig | dict[str, object] = policy
    elif policy_input == "resolved_mapping":
        policy_config = policy.to_dict()
    else:
# … caller assertions omitted …
```

2. [test fixture: `test_repeated_payout_backtest_continues_through_multiple_cycles`](../../../../tests/integration/backtest/test_repeated_payout_backtest.py#L127)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "last_swing_high": np.full(len(index), 105.0),
        },
        index=index,
    )
    actions = iter([1, 2, 1, 2, 2, 2, 2])
    policy = TradingPolicyConfig(
        mode="repeated_payout",
        operating_balance=100.0,
        profit_target_balance=101.5,
        account_floor=90.0,
        daily_loss_limit_pct=0.20,
        max_agent_risk_frac=0.009,
    ).validate()

    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions),
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `resolve_trading_policy`

**Kind:** function · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Resolve trading policy settings from an attribute-based configuration.

**Exact API:** {py:obj}`trading.policy.config.resolve_trading_policy` · **Source:** [trading/policy/config.py:194](../../../../trading/policy/config.py#L194)

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

1. [test fixture: `test_repeated_policy_config_resolves_without_changing_default`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L16)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_repeated_policy_config_resolves_without_changing_default() -> None:
    legacy = resolve_trading_policy(load_config())
    assert legacy.mode == "legacy"
    assert legacy.risk_state_schema_version == "risk-state-v1"
    assert legacy.daily_pnl_basis == "session_net_equity"
    assert legacy.daily_loss_includes_open_pnl is True
    assert legacy.daily_loss_reset_source == "supplied_session_id_transition"
# … caller assertions omitted …
```

2. [test fixture: `test_historical_dollar_account_floor_resolves_to_initial_equity_percentage`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L42)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_historical_dollar_account_floor_resolves_to_initial_equity_percentage() -> None:
    policy = resolve_trading_policy(
        {
            "account": {"initial_balance": 100_000.0},
            "trading_policy": {
                "mode": "repeated_payout",
                "repeated_payout": {
                    "operating_balance": 100_000.0,
                    "account_floor_equity": 85_000.0,
                },
            },
        }
    )

    assert policy.max_loss_limit_initial_pct == pytest.approx(0.15)
    assert policy.account_floor == pytest.approx(85_000.0)

    restored = TradingPolicyConfig.from_mapping(
# … caller assertions omitted …
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

1. [test fixture: `test_repeated_payout_backtest_withdraws_realized_overshoot_and_reports_economic_value`](../../../../tests/integration/backtest/test_repeated_payout_backtest.py#L39)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "last_swing_high": np.full(len(index), 103.0),
        },
        index=index,
    )
    actions = iter([1, 2, 2, 2, 2, 2])
    policy = TradingPolicyConfig(
        mode="repeated_payout",
        operating_balance=100.0,
        profit_target_balance=101.5,
        account_floor=90.0,
        daily_loss_limit_pct=0.20,
        max_agent_risk_frac=0.009,
    ).validate()
    if policy_input == "instance":
        policy_config: TradingPolicyConfig | dict[str, object] = policy
    elif policy_input == "resolved_mapping":
        policy_config = policy.to_dict()
    else:
# … caller assertions omitted …
```

2. [test fixture: `test_repeated_payout_backtest_continues_through_multiple_cycles`](../../../../tests/integration/backtest/test_repeated_payout_backtest.py#L127)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "last_swing_high": np.full(len(index), 105.0),
        },
        index=index,
    )
    actions = iter([1, 2, 1, 2, 2, 2, 2])
    policy = TradingPolicyConfig(
        mode="repeated_payout",
        operating_balance=100.0,
        profit_target_balance=101.5,
        account_floor=90.0,
        daily_loss_limit_pct=0.20,
        max_agent_risk_frac=0.009,
    ).validate()

    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions),
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `resolve_trading_policy`

**Kind:** function · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Resolve trading policy settings from an attribute-based configuration.

**Exact API:** {py:obj}`trading.policy.config.resolve_trading_policy` · **Source:** [trading/policy/config.py:194](../../../../trading/policy/config.py#L194)

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

1. [test fixture: `test_repeated_policy_config_resolves_without_changing_default`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L16)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_repeated_policy_config_resolves_without_changing_default() -> None:
    legacy = resolve_trading_policy(load_config())
    assert legacy.mode == "legacy"
    assert legacy.risk_state_schema_version == "risk-state-v1"
    assert legacy.daily_pnl_basis == "session_net_equity"
    assert legacy.daily_loss_includes_open_pnl is True
    assert legacy.daily_loss_reset_source == "supplied_session_id_transition"
# … caller assertions omitted …
```

2. [test fixture: `test_historical_dollar_account_floor_resolves_to_initial_equity_percentage`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L42)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_historical_dollar_account_floor_resolves_to_initial_equity_percentage() -> None:
    policy = resolve_trading_policy(
        {
            "account": {"initial_balance": 100_000.0},
            "trading_policy": {
                "mode": "repeated_payout",
                "repeated_payout": {
                    "operating_balance": 100_000.0,
                    "account_floor_equity": 85_000.0,
                },
            },
        }
    )

    assert policy.max_loss_limit_initial_pct == pytest.approx(0.15)
    assert policy.account_floor == pytest.approx(85_000.0)

    restored = TradingPolicyConfig.from_mapping(
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `resolve_trading_policy_mapping`

**Kind:** function · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Resolve trading policy settings from a mapping configuration.

**Exact API:** {py:obj}`trading.policy.config.resolve_trading_policy_mapping` · **Source:** [trading/policy/config.py:277](../../../../trading/policy/config.py#L277)

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

## `TradingPolicyConfig.daily_loss_limit`

**Kind:** method · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Return the initial-equity daily allowance in account currency.

**Exact API:** {py:obj}`trading.policy.config.TradingPolicyConfig.daily_loss_limit` · **Source:** [trading/policy/config.py:72](../../../../trading/policy/config.py#L72)

**Inputs and outputs:**

- **Returns:**

  ```text
  Daily-loss amount computed from operating balance and configured fraction.
  ```

**Observed usage:**

1. [test fixture: `test_repeated_policy_config_resolves_without_changing_default`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L31)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert TradingPolicyConfig(**repeated.to_dict()).validate() == repeated
    assert repeated.operating_balance == 100_000.0
    assert repeated.profit_target_balance == 110_000.0
    assert repeated.account_floor == 90_000.0
    assert repeated.daily_loss_limit_pct == pytest.approx(0.05)
    assert repeated.daily_loss_limit == pytest.approx(5_000.0)
    assert repeated.max_loss_limit_initial_pct == pytest.approx(0.10)
    assert repeated.max_agent_risk_frac == pytest.approx(0.009)
    repeated_block = load_config(
        ["trading_policy.mode=repeated_payout"]
    ).trading_policy.repeated_payout
# … caller assertions omitted …
```

2. [test fixture: `test_historical_dollar_daily_limit_is_normalized_to_initial_equity_fraction`](../../../../tests/unit/training/test_backtest_runner_policy.py#L40)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_historical_dollar_daily_limit_is_normalized_to_initial_equity_fraction() -> None:
    policy = TradingPolicyConfig.from_mapping(
        {
            "operating_balance": 100_000.0,
            "daily_loss_limit": 5_000.0,
            "account_floor": 90_000.0,
        }
    )

    assert policy.daily_loss_limit_pct == 0.05
    assert policy.daily_loss_limit == 5_000.0
    assert policy.account_floor == 90_000.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingPolicyConfig.from_mapping`

**Kind:** method · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Load resolved settings, converting historical dollar limits to fractions.

**Exact API:** {py:obj}`trading.policy.config.TradingPolicyConfig.from_mapping` · **Source:** [trading/policy/config.py:81](../../../../trading/policy/config.py#L81)

**Inputs and outputs:**

- **Args:**

  ```text
  values: Resolved trading-policy settings mapping.
  ```

- **Returns:**

  ```text
  Validated immutable trading-policy configuration.
  ```

**Observed usage:**

1. [test fixture: `test_historical_dollar_account_floor_resolves_to_initial_equity_percentage`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L58)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )

    assert policy.max_loss_limit_initial_pct == pytest.approx(0.15)
    assert policy.account_floor == pytest.approx(85_000.0)

    restored = TradingPolicyConfig.from_mapping(
        {
            "mode": "repeated_payout",
            "operating_balance": 100_000.0,
            "account_floor": 85_000.0,
        }
    ).validate()
    assert restored.max_loss_limit_initial_pct == pytest.approx(0.15)
    assert restored.account_floor == pytest.approx(85_000.0)
```

2. [test fixture: `test_historical_dollar_daily_limit_is_normalized_to_initial_equity_fraction`](../../../../tests/unit/training/test_backtest_runner_policy.py#L31)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_historical_dollar_daily_limit_is_normalized_to_initial_equity_fraction() -> None:
    policy = TradingPolicyConfig.from_mapping(
        {
            "operating_balance": 100_000.0,
            "daily_loss_limit": 5_000.0,
            "account_floor": 90_000.0,
        }
    )

    assert policy.daily_loss_limit_pct == 0.05
    assert policy.daily_loss_limit == 5_000.0
    assert policy.account_floor == 90_000.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingPolicyConfig.repeated_payout`

**Kind:** method · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Return whether the account policy enables repeated payouts.

**Exact API:** {py:obj}`trading.policy.config.TradingPolicyConfig.repeated_payout` · **Source:** [trading/policy/config.py:63](../../../../trading/policy/config.py#L63)

**Inputs and outputs:**

- **Returns:**

  ```text
  Whether repeated payout meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_configured_backtest_runner_resolves_static_daily_loss_semantics`](../../../../tests/unit/training/test_backtest_runner_policy.py#L17)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_configured_backtest_runner_resolves_static_daily_loss_semantics() -> None:
    cfg = load_config()

    policy = _configured_backtest_policy(cfg)
    assert policy.daily_pnl_basis == "session_net_equity"
    assert policy.daily_loss_includes_open_pnl
    assert policy.daily_loss_limit_pct == 0.05
    assert cost_model(cfg).slippage_points == float(cfg.costs.slippage_points) == 5.0
    assert not policy.repeated_payout
```

2. [test fixture: `test_configured_backtest_runner_resolves_repeated_payout_lifecycle`](../../../../tests/unit/training/test_backtest_runner_policy.py#L24)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_configured_backtest_runner_resolves_repeated_payout_lifecycle() -> None:
    cfg = load_config(["trading_policy.mode=repeated_payout"])

    policy = _configured_backtest_policy(cfg)
    assert policy.repeated_payout
    assert policy.daily_pnl_basis == "session_net_equity"
    assert policy.operating_balance == cfg.account.initial_balance
    assert policy.max_agent_risk_frac < 0.01
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingPolicyConfig.to_dict`

**Kind:** method · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Return the policy settings as a JSON-compatible mapping.

**Exact API:** {py:obj}`trading.policy.config.TradingPolicyConfig.to_dict` · **Source:** [trading/policy/config.py:185](../../../../trading/policy/config.py#L185)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_repeated_policy_config_resolves_without_changing_default`](../../../../tests/unit/trading/test_repeated_payout_policy.py#L22)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert legacy.mode == "legacy"
    assert legacy.risk_state_schema_version == "risk-state-v1"
    assert legacy.daily_pnl_basis == "session_net_equity"
    assert legacy.daily_loss_includes_open_pnl is True
    assert legacy.daily_loss_reset_source == "supplied_session_id_transition"
    assert TradingPolicyConfig(**legacy.to_dict()).validate() == legacy
    repeated = resolve_trading_policy(load_config(["trading_policy.mode=repeated_payout"]))
    assert repeated.daily_pnl_basis == "session_net_equity"
    assert repeated.daily_loss_includes_open_pnl is True
    assert TradingPolicyConfig(**repeated.to_dict()).validate() == repeated
    assert repeated.operating_balance == 100_000.0
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`

## `TradingPolicyConfig.validate`

**Kind:** method · **Status:** stable · **Owner:** `trading.policy.config`

**Purpose:** Validate payout thresholds and account-floor relationships.

**Exact API:** {py:obj}`trading.policy.config.TradingPolicyConfig.validate` · **Source:** [trading/policy/config.py:134](../../../../trading/policy/config.py#L134)

**Inputs and outputs:**

- **Returns:**

  ```text
  Result of validate payout thresholds and account-floor relationships.
  ```

**Observed usage:**

1. [test fixture: `test_repeated_payout_backtest_withdraws_realized_overshoot_and_reports_economic_value`](../../../../tests/integration/backtest/test_repeated_payout_backtest.py#L39)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "last_swing_high": np.full(len(index), 103.0),
        },
        index=index,
    )
    actions = iter([1, 2, 2, 2, 2, 2])
    policy = TradingPolicyConfig(
        mode="repeated_payout",
        operating_balance=100.0,
        profit_target_balance=101.5,
        account_floor=90.0,
        daily_loss_limit_pct=0.20,
        max_agent_risk_frac=0.009,
    ).validate()
    if policy_input == "instance":
        policy_config: TradingPolicyConfig | dict[str, object] = policy
    elif policy_input == "resolved_mapping":
        policy_config = policy.to_dict()
    else:
# … caller assertions omitted …
```

2. [test fixture: `test_repeated_payout_backtest_continues_through_multiple_cycles`](../../../../tests/integration/backtest/test_repeated_payout_backtest.py#L127)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "last_swing_high": np.full(len(index), 105.0),
        },
        index=index,
    )
    actions = iter([1, 2, 1, 2, 2, 2, 2])
    policy = TradingPolicyConfig(
        mode="repeated_payout",
        operating_balance=100.0,
        profit_target_balance=101.5,
        account_floor=90.0,
        daily_loss_limit_pct=0.20,
        max_agent_risk_frac=0.009,
    ).validate()

    result = run_backtest(
        bars,
        features,
        lambda _observation: next(actions),
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/trading/index`
