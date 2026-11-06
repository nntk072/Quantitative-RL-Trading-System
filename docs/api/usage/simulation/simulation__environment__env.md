# Simulation · `environment.env`

This page contains 5 public callable records owned by `simulation.environment.env`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TradingEnv`

**Kind:** class · **Status:** stable · **Owner:** `simulation.environment.env`

**Purpose:** RL trading environment with structure-aware SL/TP and hybrid action space.

**Exact API:** {py:obj}`simulation.environment.env.TradingEnv` · **Source:** [simulation/environment/env.py:33](../../../../simulation/environment/env.py#L33)

**Observed usage:**

1. [test fixture: `test_environment_and_backtest_reconcile_realized_and_open_account_transitions`](../../../../tests/integration/backtest/test_account_transition_parity.py#L70)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "soft_daily_loss_limit_pct": 0.0,
        "soft_max_loss_limit_initial_pct": 0.0,
    }
    actions = [1, 0, 19, 0, 1, 0, 0, 19, 1, 0, 19]

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        initial_balance=initial_balance,
        cost_model=cost_model,
        guardrail_kwargs=guardrails,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
    )
    env.reset(seed=7)
    env_open_pnl_at_mark: float | None = None
    env_account_trace_rows: list[dict[str, Any]] = []
    for action_index, action in enumerate(actions):
        _, _, _, _, info = env.step(action)
# … caller assertions omitted …
```

2. [test fixture: `test_environment_and_backtest_match_on_one_shared_tick_execution_trace`](../../../../tests/integration/backtest/test_account_transition_parity.py#L291)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        tick_times,
        np.asarray([100.0, 99.5]),
        np.asarray([100.2, 99.7]),
    )
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=2.0)
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
        initial_balance=50_000.0,
        cost_model=cost_model,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
        reward_mode="pnl",
        tickbook=tickbook,
        tick_execution_required=tick_execution_required,
        randomized_fill_latency_ms=randomized_fill_latency_ms,
        tick_fill_slippage_points=tick_slippage,
    )
    env.reset(seed=7)
    env.step(env_action)
    env.step(19)

    actions = iter((direction, 19))
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `TradingEnv`

**Kind:** class · **Status:** stable · **Owner:** `simulation.environment.env`

**Purpose:** RL trading environment with structure-aware SL/TP and hybrid action space.

**Exact API:** {py:obj}`simulation.environment.env.TradingEnv` · **Source:** [simulation/environment/env.py:33](../../../../simulation/environment/env.py#L33)

**Observed usage:**

1. [test fixture: `test_environment_and_backtest_reconcile_realized_and_open_account_transitions`](../../../../tests/integration/backtest/test_account_transition_parity.py#L70)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "soft_daily_loss_limit_pct": 0.0,
        "soft_max_loss_limit_initial_pct": 0.0,
    }
    actions = [1, 0, 19, 0, 1, 0, 0, 19, 1, 0, 19]

    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
        initial_balance=initial_balance,
        cost_model=cost_model,
        guardrail_kwargs=guardrails,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
    )
    env.reset(seed=7)
    env_open_pnl_at_mark: float | None = None
    env_account_trace_rows: list[dict[str, Any]] = []
    for action_index, action in enumerate(actions):
        _, _, _, _, info = env.step(action)
# … caller assertions omitted …
```

2. [test fixture: `test_environment_and_backtest_match_on_one_shared_tick_execution_trace`](../../../../tests/integration/backtest/test_account_transition_parity.py#L291)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        tick_times,
        np.asarray([100.0, 99.5]),
        np.asarray([100.2, 99.7]),
    )
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=2.0)
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
        initial_balance=50_000.0,
        cost_model=cost_model,
        risk_frac_range=(0.001, 0.001),
        rr_ratio_range=(1.0, 1.0),
        min_lot=0.01,
        max_lot=1.0,
        contract_size=1.0,
        max_loss_per_trade_usd=100.0,
        block_overnight=False,
        reward_mode="pnl",
        tickbook=tickbook,
        tick_execution_required=tick_execution_required,
        randomized_fill_latency_ms=randomized_fill_latency_ms,
        tick_fill_slippage_points=tick_slippage,
    )
    env.reset(seed=7)
    env.step(env_action)
    env.step(19)

    actions = iter((direction, 19))
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `TradingEnv.from_bundle`

**Kind:** method · **Status:** stable · **Owner:** `simulation.environment.env`

**Purpose:** Create an environment whose persistent market arrays are read-only mmaps.

**Exact API:** {py:obj}`simulation.environment.env.TradingEnv.from_bundle` · **Source:** [simulation/environment/env.py:386](../../../../simulation/environment/env.py#L386)

**Inputs and outputs:**

- **Args:**

  ```text
  bundle_path: Path or filename identifying the bundle.
  **kwargs: Kwargs used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of create an environment whose persistent market arrays are read-only mmaps.
  ```

**Observed usage:**

1. [test fixture: `test_bundle_env_step_trace_matches_frames`](../../../../tests/unit/simulation/test_environment/test_bundle_env_equivalence.py#L69)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        raw_columns=BaselineStrategy().raw_columns,
        feature_config_hash="equivalence-v1",
        tickbook=None,
        pre_ny_by_date=None,
    )
    shared = TradingEnv.from_bundle(bundle_path, **common)
    with pytest.raises(ValueError, match="reachable-r validity-mask mode"):
        TradingEnv.from_bundle(
            bundle_path,
            **{
                **common,
# … caller assertions omitted …
```

2. [test fixture: `test_bundle_env_without_session_id_matches_frames`](../../../../tests/unit/simulation/test_environment/test_bundle_env_equivalence.py#L148)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        raw_columns=BaselineStrategy().raw_columns,
        feature_config_hash="missing-session-id-v1",
        tickbook=None,
        pre_ny_by_date=None,
    )
    shared = TradingEnv.from_bundle(path, obs_window=10)
    left, _ = frames.reset(seed=19)
    right, _ = shared.reset(seed=19)
    for _ in range(20):
        for key in left:
            np.testing.assert_array_equal(left[key], right[key])
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `TradingEnv.step`

**Kind:** method · **Status:** stable · **Owner:** `simulation.environment.env`

**Purpose:** Gymnasium adapter for :meth:`transition`.

**Exact API:** {py:obj}`simulation.environment.env.TradingEnv.step` · **Source:** [simulation/environment/env.py:418](../../../../simulation/environment/env.py#L418)

**Inputs and outputs:**

- **Args:**

  ```text
  action: Action to apply to the current state.
  ```

- **Returns:**

  ```text
  Whether step meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_environment_and_backtest_reconcile_realized_and_open_account_transitions`](../../../../tests/integration/backtest/test_account_transition_parity.py#L89)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    env.reset(seed=7)
    env_open_pnl_at_mark: float | None = None
    env_account_trace_rows: list[dict[str, Any]] = []
    for action_index, action in enumerate(actions):
        _, _, _, _, info = env.step(action)
        env_account_trace_rows.append(info["account_state_snapshot"])
        if action_index == 6:
            env_open_pnl_at_mark = float(env.account.open_pnl)

    env_opens = [event for event in env.trade_log if event["type"] == "open"]
# … caller assertions omitted …
```

2. [test fixture: `test_environment_and_backtest_match_on_one_shared_tick_execution_trace`](../../../../tests/integration/backtest/test_account_transition_parity.py#L311)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        tick_execution_required=tick_execution_required,
        randomized_fill_latency_ms=randomized_fill_latency_ms,
        tick_fill_slippage_points=tick_slippage,
    )
    env.reset(seed=7)
    env.step(env_action)
    env.step(19)

    actions = iter((direction, 19))

    def policy(_observation: np.ndarray[Any, Any]) -> int:
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `TradingEnv.transition`

**Kind:** method · **Status:** stable · **Owner:** `simulation.environment.env`

**Purpose:** Advance the simulator through its framework-neutral transition API.

**Exact API:** {py:obj}`simulation.environment.env.TradingEnv.transition` · **Source:** [simulation/environment/env.py:432](../../../../simulation/environment/env.py#L432)

**Inputs and outputs:**

- **Args:**

  ```text
  action: Action to apply to the current state.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``np.ndarray[Any, Any]]`` values.
  ```

**Observed usage:**

1. [test fixture: `test_native_transition_matches_gymnasium_step`](../../../../tests/unit/simulation/test_environment/test_simulation_transition_contract.py#L40)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_native_transition_matches_gymnasium_step() -> None:
    bars = _make_deterministic_bars(n=96)
    features = _make_features(bars)
    native_env = TradingEnv(bars, features, obs_window=10)
    gym_env = TradingEnv(bars, features, obs_window=10)
    _assert_same(native_env.reset(seed=41), gym_env.reset(seed=41))

    native = native_env.transition(0)
    gym_result = gym_env.step(0)

    assert isinstance(native, SimulationTransition)
    _assert_same(native.as_gymnasium(), gym_result)
```

2. [production caller: `step`](../../../../simulation/environment/env.py#L430)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def step(
    self,
    action: int | float | np.ndarray[Any, Any],
) -> tuple[dict[str, np.ndarray[Any, Any]], float, bool, bool, dict[str, Any]]:
    return self.transition(action).as_gymnasium()
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`
