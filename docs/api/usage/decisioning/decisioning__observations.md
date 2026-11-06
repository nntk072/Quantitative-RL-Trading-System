# Decisioning · `observations`

This page contains 6 public callable records owned by `decisioning.observations`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ObservationSchema`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Explicit coordinate names and version for the account branch.

**Exact API:** {py:obj}`decisioning.observations.ObservationSchema` · **Source:** [decisioning/observations.py:154](../../../../decisioning/observations.py#L154)

**Observed usage:**

1. [production caller: `build_observation_schema`](../../../../decisioning/observations.py#L207)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def build_observation_schema(
    version: str = OBSERVATION_SCHEMA_V1,
    *,
    entry_state_visibility: bool = False,
) -> ObservationSchema:
    coordinates: tuple[str, ...]
    if version == OBSERVATION_SCHEMA_V1:
        coordinates = V1_COORDINATES
    elif version in (OBSERVATION_SCHEMA_V2, OBSERVATION_SCHEMA_V3):
        coordinates = V2_COORDINATES
    else:
        raise ValueError(f"unknown observation schema version: {version!r}")
    if entry_state_visibility:
        coordinates = (*coordinates, *(f"entry_state_{name.lower()}" for name in ENTRY_STATES))
    return ObservationSchema(version, coordinates, entry_state_visibility)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `build_observation_schema`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Return a named schema; never infer semantics from a vector width.

**Exact API:** {py:obj}`decisioning.observations.build_observation_schema` · **Source:** [decisioning/observations.py:184](../../../../decisioning/observations.py#L184)

**Inputs and outputs:**

- **Args:**

  ```text
  version: Text or path value identifying the version.
  entry_state_visibility: Whether to enable or require the entry state visibility.
  ```

- **Returns:**

  ```text
  Result of return a named schema; never infer semantics from a vector width.
  ```

**Observed usage:**

1. [test fixture: `test_setup_backtest_emits_versioned_account_state`](../../../../tests/integration/backtest/test_setup_mask_backtest_boundary.py#L759)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    action_schema = build_trade_setup_action_schema()
    action = np.zeros(action_schema.width, dtype=np.float32)
    action[action_schema.indices["trade_setup"]] = trade_setup_center(0)
    observation_schema = build_observation_schema(schema_version)
    captured: dict[str, Array] = {}

    def no_trade(observation: Any) -> Array:
        if not captured:
            captured.update(observation)
# … caller assertions omitted …
```

2. [test fixture: `test_scalar_backtest_entry_state_tracks_causal_candidate_and_arming`](../../../../tests/integration/backtest/test_setup_mask_backtest_boundary.py#L914)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    result = run_backtest(
        bars,
        features,
        hold,
        obs_window=1,
        observation_schema=build_observation_schema(
            OBSERVATION_SCHEMA_V1, entry_state_visibility=True
        ),
        entry_state_machine=True,
        strategy=BaselineStrategy(),
        hold_on_zero=True,
    )

# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `normalized_account_vector`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Build the legacy normalized account input coordinates.

**Exact API:** {py:obj}`decisioning.observations.normalized_account_vector` · **Source:** [decisioning/observations.py:51](../../../../decisioning/observations.py#L51)

**Inputs and outputs:**

- **Args:**

  ```text
  equity: Current account equity in account currency.
  initial_balance: Numeric value used for the initial balance.
  pos_dir: Numeric value used for the pos dir.
  open_pnl: Numeric value used for the open pnl.
  dist_to_sl: Numeric value used for the dist to sl.
  trailing_dd: Numeric value used for the trailing dd.
  close: Numeric value used for the close.
  entry_state: Entry state used by the operation described above.
  ```

- **Returns:**

  ```text
  Array returned by ``normalized_account_vector``.
  ```

**Observed usage:**

1. [test fixture: `test_normalized_account_vector_preserves_valid_legacy_coordinates`](../../../../tests/unit/decisioning/test_observations.py#L12)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_normalized_account_vector_preserves_valid_legacy_coordinates() -> None:
    values = normalized_account_vector(
        equity=99_000.0,
        initial_balance=100_000.0,
        pos_dir=-1.0,
        open_pnl=-100.0,
        dist_to_sl=10.0,
        trailing_dd=0.1,
        close=20_000.0,
        entry_state="IN_POSITION",
    )

    assert values.shape == (10,)
    assert values.dtype == np.float32
    np.testing.assert_allclose(
        values[:6], [np.log(0.99), -1.0, -0.001, -100.0 / 99_000 * 100, 0.0005, 0.1]
# … caller assertions omitted …
```

2. [test fixture: `test_normalized_account_vector_rejects_nonfinite_inputs`](../../../../tests/unit/decisioning/test_observations.py#L48)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "close": 20_000.0,
    }
    inputs[name] = float("nan")

    with pytest.raises(ValueError, match=f"input {name} must be finite"):
        normalized_account_vector(
            equity=inputs["equity"],
            initial_balance=inputs["initial_balance"],
            pos_dir=inputs["pos_dir"],
            open_pnl=inputs["open_pnl"],
            dist_to_sl=inputs["dist_to_sl"],
            trailing_dd=inputs["trailing_dd"],
            close=inputs["close"],
            entry_state=None,
        )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `pad_observation_window`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Left-pad a sequence window and mark which rows contain real events.

**Exact API:** {py:obj}`decisioning.observations.pad_observation_window` · **Source:** [decisioning/observations.py:17](../../../../decisioning/observations.py#L17)

**Inputs and outputs:**

- **Args:**

  ```text
  seq: Seq used by the operation described above.
  window: Numeric value used for the window.
  ```

- **Returns:**

  ```text
  Array returned by ``pad_observation_window``.
  ```

**Observed usage:**

1. [test fixture: `test_pad_observation_window_left_pads_two_dimensional_values_and_mask`](../../../../tests/unit/decisioning/test_observations.py#L87)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_pad_observation_window_left_pads_two_dimensional_values_and_mask() -> None:
    values, mask = pad_observation_window(np.array([[1.0, 2.0], [3.0, 4.0]]), 4)

    np.testing.assert_array_equal(values, [[0.0, 0.0], [0.0, 0.0], [1.0, 2.0], [3.0, 4.0]])
    np.testing.assert_array_equal(mask, [0.0, 0.0, 1.0, 1.0])
    assert values.dtype == np.float32
```

2. [test fixture: `test_pad_observation_window_keeps_only_the_latest_rows_when_sequence_is_long`](../../../../tests/unit/decisioning/test_observations.py#L95)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_pad_observation_window_keeps_only_the_latest_rows_when_sequence_is_long() -> None:
    values, mask = pad_observation_window(np.array([1.0, 2.0, 3.0]), 2)

    np.testing.assert_array_equal(values, [[2.0], [3.0]])
    np.testing.assert_array_equal(mask, [1.0, 1.0])
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `ObservationSchema.to_dict`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Return the ordered observation contract as JSON-compatible data.

**Exact API:** {py:obj}`decisioning.observations.ObservationSchema.to_dict` · **Source:** [decisioning/observations.py:170](../../../../decisioning/observations.py#L170)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_setup_backtest_emits_versioned_account_state`](../../../../tests/integration/backtest/test_setup_mask_backtest_boundary.py#L798)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        current_price=20_000.0,
        entry_price=0.0,
    )
    np.testing.assert_allclose(captured["account"], expected)
    assert captured["account"].shape == (28,)
    assert result["observation_schema"] == observation_schema.to_dict()
    assert result["daily_pnl_basis"] == "session_net_equity"
    assert result["daily_loss_limit_pct"] == 0.05
    assert result["daily_loss_limit_usd"] == 5_000.0

    visible_entry_state = build_observation_schema(schema_version, entry_state_visibility=True)
# … caller assertions omitted …
```

2. [test fixture: `_StubModel`](../../../../tests/unit/features/test_stage_a_observation.py#L24)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
class _StubModel:
    _observation_schema = build_observation_schema(OBSERVATION_SCHEMA_V2).to_dict()
    _action_schema = build_discrete_trading_action_schema().to_dict()
    action_space: Any = spaces.Discrete(20)

    def predict(self, obs: dict[str, Any], deterministic: bool = True) -> np.ndarray[Any, Any]:  # noqa: ARG002
        return np.array([1])
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `ObservationSchema.width`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Return the total number of flattened observation coordinates.

**Exact API:** {py:obj}`decisioning.observations.ObservationSchema.width` · **Source:** [decisioning/observations.py:162](../../../../decisioning/observations.py#L162)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``width``.
  ```

**Observed usage:**

1. [test fixture: `test_v2_schema_has_exact_named_width`](../../../../tests/unit/simulation/test_environment/test_observation_schema.py#L61)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_v2_schema_has_exact_named_width() -> None:
    schema = build_observation_schema(OBSERVATION_SCHEMA_V2)
    assert schema.width == len(V2_COORDINATES) == 28
    assert schema.coordinates == V2_COORDINATES
```

2. [production caller: `to_dict`](../../../../decisioning/observations.py#L178)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def to_dict(self) -> dict[str, Any]:
    return {
        "version": self.version,
        "observation_width": self.width,
        "observation_coordinates": list(self.coordinates),
        "entry_state_visibility": self.entry_state_visibility,
    }
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`
