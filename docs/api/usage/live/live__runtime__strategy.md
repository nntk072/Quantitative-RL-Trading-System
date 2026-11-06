# Live runtime · `runtime.strategy`

This page contains 5 public callable records owned by `live.runtime.strategy`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `RLStrategyAdapter`

**Kind:** class · **Status:** stable · **Owner:** `live.runtime.strategy`

**Purpose:** Wraps a trained SB3 model as a live-trading strategy.

**Exact API:** {py:obj}`live.runtime.strategy.RLStrategyAdapter` · **Source:** [live/runtime/strategy.py:70](../../../../live/runtime/strategy.py#L70)

**Observed usage:**

1. [test fixture: `test_train_live_observation_parity`](../../../../tests/unit/features/test_stage_a_observation.py#L120)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        observation_schema_version=OBSERVATION_SCHEMA_V2,
    )
    env.account.update_equity(-250.0)
    env_obs = env._get_observation()

    adapter = RLStrategyAdapter(
        model=_StubModel(),
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    adapter._features = features
    adapter._bars = bars
    adapter.obs_window = 10
    adapter._initial_balance = 100_000.0
    step = int(env.step_idx)
# … caller assertions omitted …
```

2. [test fixture: `test_rl_bridge_observation_contract`](../../../../tests/unit/live/test_rl_bridge.py#L194)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    from live.runtime.strategy import RLStrategyAdapter

    adapter = RLStrategyAdapter(
        model=_StubModel(),
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    adapter.update_bars(trending_bars)
    obs = adapter.build_observation({"equity": 100_000.0})
    assert set(obs) == {"seq", "seq_mask", "account"}
    assert obs["seq"].dtype == np.float32
    assert obs["account"].shape == (28,)
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/live/index`

## `RLStrategyAdapter.as_strategy`

**Kind:** method · **Status:** stable · **Owner:** `live.runtime.strategy`

**Purpose:** Return a duck-typed MT5 strategy that wraps this adapter.

**Exact API:** {py:obj}`live.runtime.strategy.RLStrategyAdapter.as_strategy` · **Source:** [live/runtime/strategy.py:354](../../../../live/runtime/strategy.py#L354)

**Inputs and outputs:**

- **Args:**

  ```text
  data_source: Primary-symbol data source returning M1 bars.
  secondary_data_source: Optional source used for secondary-symbol
      features. Supply it when the policy's configured observations
      include those features.
  ```

- **Returns:**

  ```text
  Result of return a duck-typed MT5 strategy that wraps this adapter.
  ```

**Observed usage:**

1. [test fixture: `test_rl_bridge_maps_actions_to_signals`](../../../../tests/unit/live/test_rl_bridge.py#L250)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_rl_bridge_maps_actions_to_signals(trending_bars):
    from live.runtime.strategy import RLStrategyAdapter

    adapter = RLStrategyAdapter(
        model=_StubModel(),
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    strategy = adapter.as_strategy(_StubData(trending_bars))
    symbol, sig = strategy.signal()
    assert symbol == "US100.cash"
    assert sig.value == "buy"
```

2. [test fixture: `test_account_state_v2_live_policy_fails_closed_without_snapshot`](../../../../tests/unit/live/test_rl_bridge.py#L274)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    adapter = RLStrategyAdapter(
        model=model,
        config_path=config_path,
        allow_runtime_normalization_fallback=True,
    )
    strategy = adapter.as_strategy(_StubData(trending_bars))

    symbol, signal = strategy.signal()

    assert symbol == "US100.cash"
    assert signal.value == "none"
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/live/index`

## `RLStrategyAdapter.build_observation`

**Kind:** method · **Status:** stable · **Owner:** `live.runtime.strategy`

**Purpose:** Construct the dict observation with the same contract as the env.

**Exact API:** {py:obj}`live.runtime.strategy.RLStrategyAdapter.build_observation` · **Source:** [live/runtime/strategy.py:223](../../../../live/runtime/strategy.py#L223)

**Inputs and outputs:**

- **Args:**

  ```text
  account_state: Key-value data used for the account state.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``np.ndarray[Any, Any]`` values.
  ```

**Observed usage:**

1. [test fixture: `test_train_live_observation_parity`](../../../../tests/unit/features/test_stage_a_observation.py#L130)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    adapter._features = features
    adapter._bars = bars
    adapter.obs_window = 10
    adapter._initial_balance = 100_000.0
    step = int(env.step_idx)
    live_obs = adapter.build_observation(
        {
            "equity": float(env.account.equity),
            "open_pnl": 0.0,
            "position_direction": 0.0,
            "dist_to_sl": 0.0,
            "trailing_dd": float(env.account.trailing_drawdown_pct()),
            "close": float(bars["close"].iloc[step]),
        }
    )

    assert set(env_obs) >= {"seq", "seq_mask", "account"}
    assert set(live_obs) == {"seq", "seq_mask", "account"}
    assert env_obs["seq"].shape == live_obs["seq"].shape
    assert env_obs["seq_mask"].shape == live_obs["seq_mask"].shape
# … caller assertions omitted …
```

2. [test fixture: `test_rl_bridge_observation_contract`](../../../../tests/unit/live/test_rl_bridge.py#L200)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        model=_StubModel(),
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    adapter.update_bars(trending_bars)
    obs = adapter.build_observation({"equity": 100_000.0})
    assert set(obs) == {"seq", "seq_mask", "account"}
    assert obs["seq"].dtype == np.float32
    assert obs["account"].shape == (28,)
    assert obs["seq_mask"].shape == (obs["seq"].shape[0],)
    action = adapter.predict_signal()
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/live/index`

## `RLStrategyAdapter.predict_signal`

**Kind:** method · **Status:** stable · **Owner:** `live.runtime.strategy`

**Purpose:** Run the provider and return its discrete id or scalar direction.

**Exact API:** {py:obj}`live.runtime.strategy.RLStrategyAdapter.predict_signal` · **Source:** [live/runtime/strategy.py:328](../../../../live/runtime/strategy.py#L328)

**Inputs and outputs:**

- **Args:**

  ```text
  account_state: Key-value data used for the account state.
  ```

- **Returns:**

  ```text
  Result of run the provider and return its discrete id or scalar direction.
  ```

**Observed usage:**

1. [test fixture: `test_rl_bridge_observation_contract`](../../../../tests/unit/live/test_rl_bridge.py#L205)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    obs = adapter.build_observation({"equity": 100_000.0})
    assert set(obs) == {"seq", "seq_mask", "account"}
    assert obs["seq"].dtype == np.float32
    assert obs["account"].shape == (28,)
    assert obs["seq_mask"].shape == (obs["seq"].shape[0],)
    action = adapter.predict_signal()
    assert action == 1
```

2. [test fixture: `test_rl_bridge_accepts_a_decision_provider`](../../../../tests/unit/live/test_rl_bridge.py#L238)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_rl_bridge_accepts_a_decision_provider(trending_bars):
    from live.runtime.strategy import RLStrategyAdapter

    provider = SB3DecisionProvider(
        _StubModel(),
        input_schema_version=OBSERVATION_SCHEMA_V2,
    )
    adapter = RLStrategyAdapter(
        provider=provider,
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    adapter.update_bars(trending_bars)

    assert adapter.predict_signal() == 1
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/live/index`

## `RLStrategyAdapter.update_bars`

**Kind:** method · **Status:** stable · **Owner:** `live.runtime.strategy`

**Purpose:** Feed the latest M1 bars; rebuilds features (call once per new bar).

**Exact API:** {py:obj}`live.runtime.strategy.RLStrategyAdapter.update_bars` · **Source:** [live/runtime/strategy.py:190](../../../../live/runtime/strategy.py#L190)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  secondary_bars: Market bar or price data used for feed the latest M1 bars; rebuilds features (call once per new bar).
  ```

**Observed usage:**

1. [test fixture: `test_rl_bridge_observation_contract`](../../../../tests/unit/live/test_rl_bridge.py#L199)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    adapter = RLStrategyAdapter(
        model=_StubModel(),
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    adapter.update_bars(trending_bars)
    obs = adapter.build_observation({"equity": 100_000.0})
    assert set(obs) == {"seq", "seq_mask", "account"}
    assert obs["seq"].dtype == np.float32
    assert obs["account"].shape == (28,)
    assert obs["seq_mask"].shape == (obs["seq"].shape[0],)
# … caller assertions omitted …
```

2. [test fixture: `test_rl_bridge_accepts_a_decision_provider`](../../../../tests/unit/live/test_rl_bridge.py#L236)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_rl_bridge_accepts_a_decision_provider(trending_bars):
    from live.runtime.strategy import RLStrategyAdapter

    provider = SB3DecisionProvider(
        _StubModel(),
        input_schema_version=OBSERVATION_SCHEMA_V2,
    )
    adapter = RLStrategyAdapter(
        provider=provider,
        config_path="config/base/default.yaml",
        allow_runtime_normalization_fallback=True,
    )
    adapter.update_bars(trending_bars)

    assert adapter.predict_signal() == 1
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/runtime`
- Generated package reference: {doc}`../../generated/live/index`
