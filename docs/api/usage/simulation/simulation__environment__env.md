# Simulation · `environment.env`

This page contains 5 public callable records owned by `simulation.environment.env`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TradingEnv`

**Kind:** class · **Status:** stable · **Owner:** `simulation.environment.env`

**Purpose:** RL trading environment with structure-aware SL/TP and hybrid action space.

**Exact API:** {py:obj}`simulation.environment.env.TradingEnv` · **Source:** [simulation/environment/env.py:33](../../../../simulation/environment/env.py#L33)

**Observed usage:**

1. [test fixture: `test_exit_mode_split_at_one_half`](../../../../tests/integration/backtest/test_entry_levels.py#L544)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "session": "ny",
        },
        index=idx,
    )
    feats = pd.DataFrame({"ema_21": np.full(n, 101.0)}, index=idx)
    env = TradingEnv(bars, feats, strategy_actions=True, allow_agent_sl_mode=False, obs_window=5)
    env._decode_action(np.array([0.0, 0.0, 0.0, 0.0, -0.02], dtype=np.float32), feats.iloc[0])
    assert env._selected_exit_mode == "structural"
    env._decode_action(np.array([0.0, 0.0, 0.0, 0.0, 0.02], dtype=np.float32), feats.iloc[0])
    assert env._selected_exit_mode == "ema_21"
    structural = _place(row, exit_mode="structural")
# … caller assertions omitted …
```

2. [test fixture: `test_stop_wins_when_the_same_bar_crosses_ema`](../../../../tests/integration/backtest/test_entry_levels.py#L690)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "session": "ny",
        },
        index=idx,
    )
    feats = pd.DataFrame({"ema_21": np.full(n, 101.0)}, index=idx)
    env = TradingEnv(bars, feats, strategy_actions=True, obs_window=5)
    env.position = Position(
        direction=1,
        size=1.0,
        entry_price=100.0,
        margin_used=0.0,
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

1. [test fixture: `test_exit_mode_split_at_one_half`](../../../../tests/integration/backtest/test_entry_levels.py#L544)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "session": "ny",
        },
        index=idx,
    )
    feats = pd.DataFrame({"ema_21": np.full(n, 101.0)}, index=idx)
    env = TradingEnv(bars, feats, strategy_actions=True, allow_agent_sl_mode=False, obs_window=5)
    env._decode_action(np.array([0.0, 0.0, 0.0, 0.0, -0.02], dtype=np.float32), feats.iloc[0])
    assert env._selected_exit_mode == "structural"
    env._decode_action(np.array([0.0, 0.0, 0.0, 0.0, 0.02], dtype=np.float32), feats.iloc[0])
    assert env._selected_exit_mode == "ema_21"
    structural = _place(row, exit_mode="structural")
# … caller assertions omitted …
```

2. [test fixture: `test_stop_wins_when_the_same_bar_crosses_ema`](../../../../tests/integration/backtest/test_entry_levels.py#L690)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "session": "ny",
        },
        index=idx,
    )
    feats = pd.DataFrame({"ema_21": np.full(n, 101.0)}, index=idx)
    env = TradingEnv(bars, feats, strategy_actions=True, obs_window=5)
    env.position = Position(
        direction=1,
        size=1.0,
        entry_price=100.0,
        margin_used=0.0,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `TradingEnv.from_bundle`

**Kind:** method · **Status:** stable · **Owner:** `simulation.environment.env`

**Purpose:** Create an environment whose persistent market arrays are read-only mmaps.

**Exact API:** {py:obj}`simulation.environment.env.TradingEnv.from_bundle` · **Source:** [simulation/environment/env.py:362](../../../../simulation/environment/env.py#L362)

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

1. [test fixture: `test_bundle_env_step_trace_matches_frames`](../../../../tests/unit/simulation/test_environment/test_bundle_env_equivalence.py#L60)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        raw_columns=BaselineStrategy().raw_columns,
        feature_config_hash="equivalence-v1",
        tickbook=None,
        pre_ny_by_date=None,
    )
    shared = TradingEnv.from_bundle(bundle_path, **common)
    assert "po3_ifvg_time_ns" not in frames._obs_columns
    assert "M5_sweep_high_pivot_time_ns" not in frames._obs_columns
    assert "po3_ifvg_age" in frames._obs_columns
    assert shared._obs_columns == frames._obs_columns
    obs_frames, _ = frames.reset(seed=41)
# … caller assertions omitted …
```

2. [test fixture: `test_bundle_env_without_session_id_matches_frames`](../../../../tests/unit/simulation/test_environment/test_bundle_env_equivalence.py#L130)

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

**Exact API:** {py:obj}`simulation.environment.env.TradingEnv.step` · **Source:** [simulation/environment/env.py:394](../../../../simulation/environment/env.py#L394)

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

1. [test fixture: `test_full_strategy_pipeline_runs`](../../../../tests/integration/test_strategy_integration.py#L80)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    action = np.array([0.8, 0.5, 0.7, 0.0, -1.0], dtype=np.float32)
    assert env.action_space.contains(action)

    # Step through; at least one strategy trade should be logged.
    for _ in range(len(bars) - 5):
        obs, reward, done, truncated, info = env.step(action)
        if env.position is not None:
            break
        if done or truncated:
            break

# … caller assertions omitted …
```

2. [test fixture: `test_baseline_entry_uses_strategy_validator`](../../../../tests/unit/simulation/test_environment/test_baseline_regression.py#L211)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            nonlocal called_strategy
            called_strategy = True
            return original(self_bs, direction=direction, row=row)

        monkeypatch.setattr(BaselineStrategy, "validate_entry", spy)
        env.step(1)
        assert called_strategy, "baseline entries must follow BaselineStrategy.validate_entry"
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `TradingEnv.transition`

**Kind:** method · **Status:** stable · **Owner:** `simulation.environment.env`

**Purpose:** Advance the simulator through its framework-neutral transition API.

**Exact API:** {py:obj}`simulation.environment.env.TradingEnv.transition` · **Source:** [simulation/environment/env.py:408](../../../../simulation/environment/env.py#L408)

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

2. [production caller: `step`](../../../../simulation/environment/env.py#L406)

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
