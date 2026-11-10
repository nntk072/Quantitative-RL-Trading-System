# Decisioning · `observations`

This page contains 7 public callable records owned by `decisioning.observations`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ObservationSchema`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Explicit coordinate names and version for the account branch.

**Exact API:** {py:obj}`decisioning.observations.ObservationSchema` · **Source:** [decisioning/observations.py:155](../../../../decisioning/observations.py#L155)

**Observed usage:**

1. [production caller: `build_observation_schema`](../../../../decisioning/observations.py#L208)

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
    elif version in (OBSERVATION_SCHEMA_V2, OBSERVATION_SCHEMA_REPEATED_PAYOUT):
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

**Exact API:** {py:obj}`decisioning.observations.build_observation_schema` · **Source:** [decisioning/observations.py:185](../../../../decisioning/observations.py#L185)

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

1. [test fixture: `test_setup_backtest_emits_versioned_account_state`](../../../../tests/integration/backtest/test_setup_mask_backtest_boundary.py#L761)

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

2. [test fixture: `test_scalar_backtest_entry_state_tracks_causal_candidate_and_arming`](../../../../tests/integration/backtest/test_setup_mask_backtest_boundary.py#L916)

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

1. [test fixture: `test_normalized_account_vector_preserves_valid_legacy_coordinates`](../../../../tests/unit/decisioning/test_observations.py#L42)

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

2. [test fixture: `test_normalized_account_vector_rejects_nonfinite_inputs`](../../../../tests/unit/decisioning/test_observations.py#L78)

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

1. [test fixture: `test_pad_observation_window_left_pads_two_dimensional_values_and_mask`](../../../../tests/unit/decisioning/test_observations.py#L117)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_pad_observation_window_left_pads_two_dimensional_values_and_mask() -> None:
    values, mask = pad_observation_window(np.array([[1.0, 2.0], [3.0, 4.0]]), 4)

    np.testing.assert_array_equal(values, [[0.0, 0.0], [0.0, 0.0], [1.0, 2.0], [3.0, 4.0]])
    np.testing.assert_array_equal(mask, [0.0, 0.0, 1.0, 1.0])
    assert values.dtype == np.float32
```

2. [test fixture: `test_pad_observation_window_keeps_only_the_latest_rows_when_sequence_is_long`](../../../../tests/unit/decisioning/test_observations.py#L125)

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

## `requires_normalized_account_observation`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Whether an account observation schema requires normalized account values.

**Exact API:** {py:obj}`decisioning.observations.requires_normalized_account_observation` · **Source:** [decisioning/observations.py:222](../../../../decisioning/observations.py#L222)

**Observed usage:**

1. [test fixture: `test_repeated_payout_schema_uses_domain_name_and_accepts_legacy_checkpoint`](../../../../tests/unit/decisioning/test_observations.py#L33)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        == expected.version
    )
    with pytest.raises(ValueError, match="unknown observation schema version"):
        build_observation_schema(_LEGACY_REPEATED_PAYOUT_SCHEMA_ID)
    assert expected.width == 28
    assert requires_normalized_account_observation(expected.version)
    validate_observation_schema(legacy_checkpoint, expected)

    legacy_checkpoint["observation_coordinates"] = ["equity"]
    with pytest.raises(ValueError, match="differs from requested environment schema"):
        validate_observation_schema(legacy_checkpoint, expected)
```

2. [production caller: `build_observation`](../../../../live/runtime/strategy.py#L252)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        pos_dir = float(st.get("position_direction", 0.0))
        open_pnl = float(st.get("open_pnl", 0.0))
        dist_to_sl = float(st.get("dist_to_sl", 0.0))
        trailing_dd = float(st.get("trailing_dd", 0.0))
        close = float(st.get("close", self._last_close))
        if requires_normalized_account_observation(self._observation_schema.version):
            required = {
                "planned_risk_usd",
                "trailing_drawdown_limit",
                "daily_loss",
                "daily_loss_limit",
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `ObservationSchema.to_dict`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Return the ordered observation contract as JSON-compatible data.

**Exact API:** {py:obj}`decisioning.observations.ObservationSchema.to_dict` · **Source:** [decisioning/observations.py:171](../../../../decisioning/observations.py#L171)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_setup_backtest_emits_versioned_account_state`](../../../../tests/integration/backtest/test_setup_mask_backtest_boundary.py#L800)

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

2. [test fixture: `test_repeated_payout_schema_uses_domain_name_and_accepts_legacy_checkpoint`](../../../../tests/unit/decisioning/test_observations.py#L22)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_repeated_payout_schema_uses_domain_name_and_accepts_legacy_checkpoint() -> None:
    expected = build_observation_schema(OBSERVATION_SCHEMA_REPEATED_PAYOUT)
    legacy_checkpoint = expected.to_dict()
    legacy_checkpoint["version"] = _LEGACY_REPEATED_PAYOUT_SCHEMA_ID

    assert expected.version == OBSERVATION_SCHEMA_REPEATED_PAYOUT
    assert (
        _canonicalize_saved_observation_schema_id(_LEGACY_REPEATED_PAYOUT_SCHEMA_ID)
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `ObservationSchema.width`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.observations`

**Purpose:** Return the total number of flattened observation coordinates.

**Exact API:** {py:obj}`decisioning.observations.ObservationSchema.width` · **Source:** [decisioning/observations.py:163](../../../../decisioning/observations.py#L163)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``width``.
  ```

**Observed usage:**

1. [test fixture: `test_repeated_payout_schema_uses_domain_name_and_accepts_legacy_checkpoint`](../../../../tests/unit/decisioning/test_observations.py#L32)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        _canonicalize_saved_observation_schema_id(_LEGACY_REPEATED_PAYOUT_SCHEMA_ID)
        == expected.version
    )
    with pytest.raises(ValueError, match="unknown observation schema version"):
        build_observation_schema(_LEGACY_REPEATED_PAYOUT_SCHEMA_ID)
    assert expected.width == 28
    assert requires_normalized_account_observation(expected.version)
    validate_observation_schema(legacy_checkpoint, expected)

    legacy_checkpoint["observation_coordinates"] = ["equity"]
    with pytest.raises(ValueError, match="differs from requested environment schema"):
# … caller assertions omitted …
```

2. [test fixture: `test_v2_schema_has_exact_named_width`](../../../../tests/unit/simulation/test_environment/test_observation_schema.py#L61)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_v2_schema_has_exact_named_width() -> None:
    schema = build_observation_schema(OBSERVATION_SCHEMA_V2)
    assert schema.width == len(V2_COORDINATES) == 28
    assert schema.coordinates == V2_COORDINATES
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`
