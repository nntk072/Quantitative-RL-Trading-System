# Decisioning · `actions`

This page contains 12 public callable records owned by `decisioning.actions`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ActionSchema`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Ordered continuous and categorical action-coordinate contract.

**Exact API:** {py:obj}`decisioning.actions.ActionSchema` · **Source:** [decisioning/actions.py:94](../../../../decisioning/actions.py#L94)

**Inputs and outputs:**

**Observed usage:**

1. [production caller: `build_action_schema`](../../../../decisioning/actions.py#L219)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    if has_tp_mode:
        coordinates.append("tp_mode")
    if has_simplex:
        coordinates.extend(("z1", "z2"))
    coordinates.append("exit")
    return ActionSchema(
        names=tuple(coordinates),
        has_direction=has_direction,
        has_sl_mode=has_sl_mode,
        has_tp_mode=has_tp_mode,
        has_multi_tp=has_multi_tp,
        has_simplex=has_simplex,
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `DiscreteActionSchema`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Named categorical actions for the legacy 20-action trading interface.

**Exact API:** {py:obj}`decisioning.actions.DiscreteActionSchema` · **Source:** [decisioning/actions.py:22](../../../../decisioning/actions.py#L22)

**Observed usage:**

1. [production caller: `build_discrete_trading_action_schema`](../../../../decisioning/actions.py#L90)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        for direction in ("long", "short")
        for risk in risk_levels
        for rr in rr_levels
    )
    names.append("exit")
    return DiscreteActionSchema(tuple(names))
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `build_action_schema`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Build the ordered action schema for a selected set of strategy controls.

**Exact API:** {py:obj}`decisioning.actions.build_action_schema` · **Source:** [decisioning/actions.py:185](../../../../decisioning/actions.py#L185)

**Inputs and outputs:**

- **Args:**

  ```text
  has_direction: Include an explicit long/short coordinate.
  has_sl_mode: Include stop-loss mode selection.
  has_tp_mode: Include take-profit mode selection.
  has_multi_tp: Include multiple target selection.
  has_simplex: Include simplex target-allocation coordinates.
  ```

- **Returns:**

  ```text
  Schema with canonical coordinate order and version.
  ```

**Observed usage:**

1. [test fixture: `test_decision_log_uses_action_schema_indices`](../../../../tests/integration/test_action_schema_contract.py#L30)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_decision_log_uses_action_schema_indices(flags: dict[str, bool]) -> None:
    schema = build_action_schema(**flags)
    raw = np.linspace(-0.9, 0.9, schema.width, dtype=np.float32)
    unit = (raw + 1.0) / 2.0
    record = _decision_from_action(raw, unit, schema)
    for name, idx in schema.indices.items():
        if name == "target":
            assert record["action_target"] == pytest.approx(raw[idx])
        else:
            assert record[f"action_{name}"] == pytest.approx(raw[idx])
    assert record["exit_u"] == pytest.approx(unit[schema.indices["exit"]])
```

2. [test fixture: `test_decoder_rejects_action_shape_that_disagrees_with_flags`](../../../../tests/integration/test_action_schema_contract.py#L43)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_decoder_rejects_action_shape_that_disagrees_with_flags() -> None:
    schema = build_action_schema(has_sl_mode=True, has_tp_mode=True, has_multi_tp=True)
    env: Any = SimpleNamespace(
        strategy_actions=True,
        action_schema=schema,
        _current_decision_id="episode-0-decision-0",
    )
    with pytest.raises(ValueError, match="action width"):
        TradingEnv._decode_action(env, np.zeros(schema.width - 1, dtype=np.float32))
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `build_action_schema_from_config`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Build the Box action schema shared by training, replay, and reports.

**Exact API:** {py:obj}`decisioning.actions.build_action_schema_from_config` · **Source:** [decisioning/actions.py:229](../../../../decisioning/actions.py#L229)

**Inputs and outputs:**

- **Args:**

  ```text
  env_config: Environment action settings from the resolved run config.
  ```

- **Returns:**

  ```text
  Scalar or trade-setup action schema matching the configured coordinates.
  ```

**Observed usage:**

1. [test fixture: `test_configured_trade_setup_schema_includes_selected_entry_execution`](../../../../tests/unit/decisioning/test_action_schema_config.py#L10)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_configured_trade_setup_schema_includes_selected_entry_execution() -> None:
    schema = build_action_schema_from_config(
        {
            "trade_setup_actions": True,
            "agent_entry_execution": True,
            "allow_agent_sl_mode": True,
            "allow_agent_tp_mode": True,
            "allow_multi_tp": False,
        }
    )

    assert schema == build_trade_setup_action_schema(
        has_sl_mode=True,
        has_tp_mode=True,
        has_multi_tp=False,
# … caller assertions omitted …
```

2. [test fixture: `test_configured_market_only_trade_setup_omits_execution_controls`](../../../../tests/unit/decisioning/test_action_schema_config.py#L29)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_configured_market_only_trade_setup_omits_execution_controls() -> None:
    schema = build_action_schema_from_config(
        {"trade_setup_actions": True, "agent_entry_execution": False}
    )

    assert schema == build_trade_setup_action_schema(
        has_entry_execution=False,
        has_sl_mode=True,
    )
    assert "entry_execution" not in schema.indices
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `build_discrete_trading_action_schema`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Describe the exact categorical menu used by ``TradingEnv`` Discrete(20).

**Exact API:** {py:obj}`decisioning.actions.build_discrete_trading_action_schema` · **Source:** [decisioning/actions.py:67](../../../../decisioning/actions.py#L67)

**Inputs and outputs:**

- **Args:**

  ```text
  n_actions: Numeric value used for the n actions.
  ```

- **Returns:**

  ```text
  Result of describe the exact categorical menu used by ``TradingEnv`` Discrete(20).
  ```

**Observed usage:**

1. [test fixture: `test_discrete_action_schema_is_the_fixed_twenty_choice_menu`](../../../../tests/unit/decisioning/test_trade_setup_properties.py#L34)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_discrete_action_schema_is_the_fixed_twenty_choice_menu() -> None:
    schema = build_discrete_trading_action_schema()

    assert schema.width == 20
    assert schema.key == "discrete-20"
    assert schema.names[0] == "hold"
    assert schema.names[-1] == "exit"
    assert len(set(schema.names)) == 20
    with pytest.raises(ValueError, match="requires 20 choices"):
        build_discrete_trading_action_schema(n_actions=19)
```

2. [test fixture: `test_position_targets_emit_explicit_holds_exits_and_delayed_reversals`](../../../../tests/unit/evaluation/test_baseline_signal_actions.py#L19)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    index = pd.RangeIndex(9)
    targets = pd.Series([0, 1, 1, 0, -1, -1, 1, 1, 0], index=index)

    actions = discrete_actions_for_position_targets(targets)

    schema = build_discrete_trading_action_schema()
    long_action = schema.names.index("enter_long_risk_high_rr_low")
    short_action = schema.names.index("enter_short_risk_high_rr_low")
    exit_action = schema.names.index("exit")
    assert actions.tolist() == [
        0,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `ActionSchema.indices`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Map every coordinate name to its position in the action vector.

**Exact API:** {py:obj}`decisioning.actions.ActionSchema.indices` · **Source:** [decisioning/actions.py:125](../../../../decisioning/actions.py#L125)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``int`` values.
  ```

**Observed usage:**

1. [test fixture: `test_decision_log_uses_action_schema_indices`](../../../../tests/integration/test_action_schema_contract.py#L34)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_decision_log_uses_action_schema_indices(flags: dict[str, bool]) -> None:
    schema = build_action_schema(**flags)
    raw = np.linspace(-0.9, 0.9, schema.width, dtype=np.float32)
    unit = (raw + 1.0) / 2.0
    record = _decision_from_action(raw, unit, schema)
    for name, idx in schema.indices.items():
        if name == "target":
            assert record["action_target"] == pytest.approx(raw[idx])
        else:
            assert record[f"action_{name}"] == pytest.approx(raw[idx])
    assert record["exit_u"] == pytest.approx(unit[schema.indices["exit"]])
```

2. [test fixture: `test_action_schema_flag_combinations_have_unique_coordinates`](../../../../tests/unit/decisioning/test_trade_setup_properties.py#L87)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        has_simplex=has_simplex,
    )

    assert len(schema.names) == schema.width == len(set(schema.names))
    assert schema.names[0] == "trade_setup"
    assert schema.indices["trade_setup"] == 0
    assert ("sl_mode" in schema.names) is has_sl
    assert ("tp_mode" in schema.names) is has_tp
    assert ("z1" in schema.names) is has_simplex
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `ActionSchema.key`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Return the canonical key describing the enabled coordinate flags.

**Exact API:** {py:obj}`decisioning.actions.ActionSchema.key` · **Source:** [decisioning/actions.py:137](../../../../decisioning/actions.py#L137)

**Inputs and outputs:**

- **Returns:**

  ```text
  Text returned by ``key``.
  ```

**Observed usage:**

1. [test fixture: `test_discrete_action_schema_is_the_fixed_twenty_choice_menu`](../../../../tests/unit/decisioning/test_trade_setup_properties.py#L37)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_discrete_action_schema_is_the_fixed_twenty_choice_menu() -> None:
    schema = build_discrete_trading_action_schema()

    assert schema.width == 20
    assert schema.key == "discrete-20"
    assert schema.names[0] == "hold"
    assert schema.names[-1] == "exit"
    assert len(set(schema.names)) == 20
    with pytest.raises(ValueError, match="requires 20 choices"):
        build_discrete_trading_action_schema(n_actions=19)
```

2. [test fixture: `test_action_schema_flag_combinations_keep_order_and_json_contract`](../../../../tests/unit/decisioning/test_trade_setup_properties.py#L140)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    expected_coordinates.append("exit")

    serialized = json.loads(json.dumps(schema.to_dict()))
    expected_contract = {
        "version": schema.version,
        "key": schema.key,
        "width": len(expected_coordinates),
        "coordinates": expected_coordinates,
        "has_direction": has_direction,
        "has_sl_mode": has_sl_mode,
        "has_tp_mode": has_tp_mode,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `ActionSchema.to_dict`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Return the complete JSON-safe coordinate contract.

**Exact API:** {py:obj}`decisioning.actions.ActionSchema.to_dict` · **Source:** [decisioning/actions.py:166](../../../../decisioning/actions.py#L166)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``object`` values.
  ```

**Observed usage:**

1. [test fixture: `test_action_schema_flag_combinations_keep_order_and_json_contract`](../../../../tests/unit/decisioning/test_trade_setup_properties.py#L137)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        expected_coordinates.append("tp_mode")
    if has_simplex:
        expected_coordinates.extend(("z1", "z2"))
    expected_coordinates.append("exit")

    serialized = json.loads(json.dumps(schema.to_dict()))
    expected_contract = {
        "version": schema.version,
        "key": schema.key,
        "width": len(expected_coordinates),
        "coordinates": expected_coordinates,
# … caller assertions omitted …
```

2. [test fixture: `test_discrete_checkpoint_requires_and_validates_named_categories`](../../../../tests/unit/models/test_action_schema_checkpoint.py#L113)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_discrete_checkpoint_requires_and_validates_named_categories() -> None:
    schema = build_discrete_trading_action_schema()
    model = SimpleNamespace(action_space=spaces.Discrete(schema.width), policy=SimpleNamespace())
    with pytest.raises(ValueError, match="unversioned discrete"):
        validate_model_discrete_action_schema(model, schema, schema.to_dict())

    bind_discrete_action_schema(model, schema)

    assert validate_model_discrete_action_schema(model, schema, schema.to_dict()) == "verified"
    assert model._action_schema["coordinates"][0] == "hold"
    assert model._action_schema["coordinates"][1] == "enter_long_risk_low_rr_low"
    assert model._action_schema["coordinates"][10] == "enter_short_risk_low_rr_low"
    assert model._action_schema["coordinates"][-1] == "exit"
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `ActionSchema.width`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Return the number of action coordinates.

**Exact API:** {py:obj}`decisioning.actions.ActionSchema.width` · **Source:** [decisioning/actions.py:116](../../../../decisioning/actions.py#L116)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``width``.
  ```

**Observed usage:**

1. [test fixture: `test_decision_log_uses_action_schema_indices`](../../../../tests/integration/test_action_schema_contract.py#L31)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_decision_log_uses_action_schema_indices(flags: dict[str, bool]) -> None:
    schema = build_action_schema(**flags)
    raw = np.linspace(-0.9, 0.9, schema.width, dtype=np.float32)
    unit = (raw + 1.0) / 2.0
    record = _decision_from_action(raw, unit, schema)
    for name, idx in schema.indices.items():
        if name == "target":
            assert record["action_target"] == pytest.approx(raw[idx])
        else:
            assert record[f"action_{name}"] == pytest.approx(raw[idx])
    assert record["exit_u"] == pytest.approx(unit[schema.indices["exit"]])
```

2. [test fixture: `test_decoder_rejects_action_shape_that_disagrees_with_flags`](../../../../tests/integration/test_action_schema_contract.py#L50)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_decoder_rejects_action_shape_that_disagrees_with_flags() -> None:
    schema = build_action_schema(has_sl_mode=True, has_tp_mode=True, has_multi_tp=True)
    env: Any = SimpleNamespace(
        strategy_actions=True,
        action_schema=schema,
        _current_decision_id="episode-0-decision-0",
    )
    with pytest.raises(ValueError, match="action width"):
        TradingEnv._decode_action(env, np.zeros(schema.width - 1, dtype=np.float32))
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `DiscreteActionSchema.key`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Return the stable key for this categorical action menu.

**Exact API:** {py:obj}`decisioning.actions.DiscreteActionSchema.key` · **Source:** [decisioning/actions.py:38](../../../../decisioning/actions.py#L38)

**Inputs and outputs:**

- **Returns:**

  ```text
  Text returned by ``key``.
  ```

**Observed usage:**

1. [test fixture: `test_version_and_layout_survive_sb3_save_load_without_training`](../../../../tests/unit/models/test_action_schema_sb3_roundtrip.py#L58)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_version_and_layout_survive_sb3_save_load_without_training(tmp_path):
    schema = build_action_schema(has_direction=True)
    model = PPO("MlpPolicy", _TinyEnv(), n_steps=2, batch_size=2, device="cpu")
    setattr(model, "_action_schema_version", schema.version)
    setattr(model, "_action_layout_key", schema.key)
    path = tmp_path / "schema_saved.zip"
    model.save(path)

    loaded = PPO.load(path, device="cpu")
    assert getattr(loaded, "_action_schema_version") == schema.version
# … caller assertions omitted …
```

2. [production caller: `to_dict`](../../../../decisioning/actions.py#L55)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def to_dict(self) -> dict[str, object]:
    return {
        "kind": "discrete",
        "version": self.version,
        "key": self.key,
        "width": self.width,
        "n_actions": self.width,
        "coordinates": list(self.names),
        "has_direction": False,
        "has_sl_mode": False,
        "has_tp_mode": False,
        "has_multi_tp": False,
        "has_simplex": False,
    }
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `DiscreteActionSchema.to_dict`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Return the complete ordered category contract.

**Exact API:** {py:obj}`decisioning.actions.DiscreteActionSchema.to_dict` · **Source:** [decisioning/actions.py:46](../../../../decisioning/actions.py#L46)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``object`` values.
  ```

**Observed usage:**

1. [test fixture: `__init__`](../../../../tests/unit/evaluation/test_rollout.py#L45)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def __init__(self, script: dict[int, int], default: int = 0):
    self.script = script
    self.default = default
    self.t = 0
    self.action_space: spaces.Space[Any] = spaces.Discrete(20)
    self._action_schema: dict[str, object] = build_discrete_trading_action_schema().to_dict()
```

2. [test fixture: `_StubModel`](../../../../tests/unit/features/test_stage_a_observation.py#L25)

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

## `DiscreteActionSchema.width`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Number of categorical choices in the discrete action space.

**Exact API:** {py:obj}`decisioning.actions.DiscreteActionSchema.width` · **Source:** [decisioning/actions.py:29](../../../../decisioning/actions.py#L29)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``width``.
  ```

**Observed usage:**

1. [test fixture: `test_version_and_layout_survive_sb3_save_load_without_training`](../../../../tests/unit/models/test_action_schema_sb3_roundtrip.py#L68)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert getattr(loaded, "_action_schema_version") == schema.version
    assert getattr(loaded, "_action_layout_key") == schema.key
    validate_model_action_schema(loaded, schema)

    same_width_other_layout = build_action_schema(has_sl_mode=True)
    assert same_width_other_layout.width == schema.width
    with pytest.raises(ValueError, match="layout"):
        validate_model_action_schema(loaded, same_width_other_layout)
```

2. [production caller: `key`](../../../../decisioning/actions.py#L44)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def key(self) -> str:
    return f"discrete-{self.width}"
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`
