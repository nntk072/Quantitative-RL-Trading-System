# Decisioning · `actions`

This page contains 11 public callable records owned by `decisioning.actions`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ActionSchema`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Ordered continuous and categorical action-coordinate contract.

**Exact API:** {py:obj}`decisioning.actions.ActionSchema` · **Source:** [decisioning/actions.py:89](../../../../decisioning/actions.py#L89)

**Inputs and outputs:**

**Observed usage:**

1. [production caller: `build_action_schema`](../../../../decisioning/actions.py#L214)

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

**Exact API:** {py:obj}`decisioning.actions.DiscreteActionSchema` · **Source:** [decisioning/actions.py:17](../../../../decisioning/actions.py#L17)

**Observed usage:**

1. [production caller: `build_discrete_trading_action_schema`](../../../../decisioning/actions.py#L85)

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

**Exact API:** {py:obj}`decisioning.actions.build_action_schema` · **Source:** [decisioning/actions.py:180](../../../../decisioning/actions.py#L180)

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
    env: Any = SimpleNamespace(strategy_actions=True, action_schema=schema)
    with pytest.raises(ValueError, match="action width"):
        TradingEnv._decode_action(env, np.zeros(schema.width - 1, dtype=np.float32))
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `build_discrete_trading_action_schema`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Describe the exact categorical menu used by ``TradingEnv`` Discrete(20).

**Exact API:** {py:obj}`decisioning.actions.build_discrete_trading_action_schema` · **Source:** [decisioning/actions.py:62](../../../../decisioning/actions.py#L62)

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

2. [test fixture: `__init__`](../../../../tests/unit/evaluation/test_rollout.py#L38)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def __init__(self, script: dict[int, int], default: int = 0):
    self.script = script
    self.default = default
    self.t = 0
    self.action_space: spaces.Space[Any] = spaces.Discrete(20)
    self._action_schema: dict[str, object] = build_discrete_trading_action_schema().to_dict()
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `ActionSchema.indices`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.actions`

**Purpose:** Map every coordinate name to its position in the action vector.

**Exact API:** {py:obj}`decisioning.actions.ActionSchema.indices` · **Source:** [decisioning/actions.py:120](../../../../decisioning/actions.py#L120)

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

**Exact API:** {py:obj}`decisioning.actions.ActionSchema.key` · **Source:** [decisioning/actions.py:132](../../../../decisioning/actions.py#L132)

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

**Exact API:** {py:obj}`decisioning.actions.ActionSchema.to_dict` · **Source:** [decisioning/actions.py:161](../../../../decisioning/actions.py#L161)

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

**Exact API:** {py:obj}`decisioning.actions.ActionSchema.width` · **Source:** [decisioning/actions.py:111](../../../../decisioning/actions.py#L111)

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

2. [test fixture: `test_decoder_rejects_action_shape_that_disagrees_with_flags`](../../../../tests/integration/test_action_schema_contract.py#L46)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_decoder_rejects_action_shape_that_disagrees_with_flags() -> None:
    schema = build_action_schema(has_sl_mode=True, has_tp_mode=True, has_multi_tp=True)
    env: Any = SimpleNamespace(strategy_actions=True, action_schema=schema)
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

**Exact API:** {py:obj}`decisioning.actions.DiscreteActionSchema.key` · **Source:** [decisioning/actions.py:33](../../../../decisioning/actions.py#L33)

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

2. [production caller: `to_dict`](../../../../decisioning/actions.py#L50)

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

**Exact API:** {py:obj}`decisioning.actions.DiscreteActionSchema.to_dict` · **Source:** [decisioning/actions.py:41](../../../../decisioning/actions.py#L41)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``object`` values.
  ```

**Observed usage:**

1. [test fixture: `__init__`](../../../../tests/unit/evaluation/test_rollout.py#L38)

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
    _observation_schema = build_observation_schema(OBSERVATION_SCHEMA_V1).to_dict()
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

**Exact API:** {py:obj}`decisioning.actions.DiscreteActionSchema.width` · **Source:** [decisioning/actions.py:24](../../../../decisioning/actions.py#L24)

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

2. [production caller: `key`](../../../../decisioning/actions.py#L39)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def key(self) -> str:
    return f"discrete-{self.width}"
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`
