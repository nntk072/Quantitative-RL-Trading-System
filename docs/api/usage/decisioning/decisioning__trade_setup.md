# Decisioning · `trade_setup`

This page contains 14 public callable records owned by `decisioning.trade_setup`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TradeSetupActionSchema`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Versioned Box action layout whose first coordinate selects a setup.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupActionSchema` · **Source:** [decisioning/trade_setup.py:45](../../../../decisioning/trade_setup.py#L45)

**Observed usage:**

1. [production caller: `build_trade_setup_action_schema`](../../../../decisioning/trade_setup.py#L140)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    if has_tp_mode:
        coordinates.append("tp_mode")
    if has_simplex:
        coordinates.extend(("z1", "z2"))
    coordinates.append("exit")
    return TradeSetupActionSchema(
        names=tuple(coordinates),
        has_sl_mode=has_sl_mode,
        has_tp_mode=has_tp_mode,
        has_multi_tp=has_multi_tp,
        has_simplex=has_simplex,
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `TradeSetupCandidate`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** One stable policy choice: idea, setup timeframe, direction, or no-trade.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupCandidate` · **Source:** [decisioning/trade_setup.py:26](../../../../decisioning/trade_setup.py#L26)

**Observed usage:**

1. [production caller: `_catalog`](../../../../decisioning/trade_setup.py#L155)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _catalog() -> tuple[TradeSetupCandidate, ...]:
    candidates = [TradeSetupCandidate(NO_TRADE_ID, None, None, 0)]
    for direction in TRADE_SETUP_DIRECTIONS:
        for idea in TRADE_SETUP_IDEAS:
            for timeframe in TRADE_SETUP_TIMEFRAMES:
                candidates.append(TradeSetupCandidate(len(candidates), idea, timeframe, direction))
    return tuple(candidates)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `build_trade_setup_action_schema`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Create the versioned action layout for primary trade-setup selection.

**Exact API:** {py:obj}`decisioning.trade_setup.build_trade_setup_action_schema` · **Source:** [decisioning/trade_setup.py:111](../../../../decisioning/trade_setup.py#L111)

**Inputs and outputs:**

- **Args:**

  ```text
  has_sl_mode: Whether to enable or require the has sl mode.
  has_tp_mode: Whether to enable or require the has tp mode.
  has_multi_tp: Whether to enable or require the has multi tp.
  has_simplex: Whether to enable or require the has simplex.
  ```

- **Returns:**

  ```text
  Result of create the versioned action layout for primary trade-setup selection.
  ```

**Observed usage:**

1. [test fixture: `test_trade_setup_action_schema_uses_canonical_coordinate_order`](../../../../tests/integration/test_trade_setup.py#L66)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trade_setup_action_schema_uses_canonical_coordinate_order() -> None:
    schema = build_trade_setup_action_schema(
        has_sl_mode=True,
        has_tp_mode=True,
        has_multi_tp=True,
        has_simplex=True,
    )
    assert schema.version == "trade-setup-overlay-action-v1"
    assert "trade_setup" in schema.names
    assert schema.names == (
        "trade_setup",
        "stop",
# … caller assertions omitted …
```

2. [test fixture: `test_action_and_observation_schemas_use_canonical_coordinates`](../../../../tests/unit/decisioning/test_trade_setup_contract.py#L42)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_action_and_observation_schemas_use_canonical_coordinates() -> None:
    action_schema = build_trade_setup_action_schema(
        has_sl_mode=True, has_tp_mode=True, has_multi_tp=True, has_simplex=True
    )
    assert action_schema.names == (
        "trade_setup",
        "stop",
        "risk",
        "tp1_sel",
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `trade_setup_candidate`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Return a setup entry by ID, rejecting unknown IDs.

**Exact API:** {py:obj}`decisioning.trade_setup.trade_setup_candidate` · **Source:** [decisioning/trade_setup.py:170](../../../../decisioning/trade_setup.py#L170)

**Inputs and outputs:**

- **Args:**

  ```text
  candidate_id: Numeric value used for the candidate id.
  ```

- **Returns:**

  ```text
  Result of return a setup entry by ID, rejecting unknown IDs.
  ```

**Observed usage:**

1. [test fixture: `test_strategy_order_uses_setup_floor_for_stops_and_all_timeframes_for_targets`](../../../../tests/integration/backtest/test_entry_levels.py#L243)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        last_swing_high=107.5,
        M3_last_swing_high=108.0,
        M5_last_swing_high=109.0,
        H1_last_swing_high=110.0,
    )
    trade_setup = trade_setup_candidate(trade_setup_candidate_id("fvg_retest", "M5", 1))
    geometry = place_strategy_order(
        _Menu(),
        direction=1,
        entry_price=100.0,
        feat_row=row,
# … caller assertions omitted …
```

2. [test fixture: `test_standard_deviation_trade_setup_uses_its_own_timeframe_level_one_stop`](../../../../tests/integration/backtest/test_entry_levels.py#L281)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        M5_last_swing_low=94.0,
        H1_last_swing_low=90.0,
        M5_last_swing_high=105.0,
        H1_last_swing_high=108.0,
    )
    trade_setup = trade_setup_candidate(trade_setup_candidate_id("standard_deviation", "M5", 1))
    geometry = place_strategy_order(
        _Menu(),
        direction=1,
        entry_price=100.0,
        feat_row=row,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `trade_setup_candidate_id`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Resolve an exact idea/timeframe/direction tuple to its stable ID.

**Exact API:** {py:obj}`decisioning.trade_setup.trade_setup_candidate_id` · **Source:** [decisioning/trade_setup.py:186](../../../../decisioning/trade_setup.py#L186)

**Inputs and outputs:**

- **Args:**

  ```text
  idea: Text or path value identifying the idea.
  setup_timeframe: Text or path value identifying the setup timeframe.
  direction: Signed trade direction: 1 for long and -1 for short.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``trade_setup_candidate_id``.
  ```

**Observed usage:**

1. [test fixture: `test_strategy_order_uses_setup_floor_for_stops_and_all_timeframes_for_targets`](../../../../tests/integration/backtest/test_entry_levels.py#L243)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        last_swing_high=107.5,
        M3_last_swing_high=108.0,
        M5_last_swing_high=109.0,
        H1_last_swing_high=110.0,
    )
    trade_setup = trade_setup_candidate(trade_setup_candidate_id("fvg_retest", "M5", 1))
    geometry = place_strategy_order(
        _Menu(),
        direction=1,
        entry_price=100.0,
        feat_row=row,
# … caller assertions omitted …
```

2. [test fixture: `test_standard_deviation_trade_setup_uses_its_own_timeframe_level_one_stop`](../../../../tests/integration/backtest/test_entry_levels.py#L281)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        M5_last_swing_low=94.0,
        H1_last_swing_low=90.0,
        M5_last_swing_high=105.0,
        H1_last_swing_high=108.0,
    )
    trade_setup = trade_setup_candidate(trade_setup_candidate_id("standard_deviation", "M5", 1))
    geometry = place_strategy_order(
        _Menu(),
        direction=1,
        entry_price=100.0,
        feat_row=row,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `trade_setup_center`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Encode an ID at the center of its equal-width Box interval.

**Exact API:** {py:obj}`decisioning.trade_setup.trade_setup_center` · **Source:** [decisioning/trade_setup.py:205](../../../../decisioning/trade_setup.py#L205)

**Inputs and outputs:**

- **Args:**

  ```text
  candidate_id: Numeric value used for the candidate id.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``trade_setup_center``.
  ```

**Observed usage:**

1. [test fixture: `test_trade_setup_ids_and_box_centers_round_trip_exactly`](../../../../tests/integration/test_trade_setup.py#L53)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trade_setup_ids_and_box_centers_round_trip_exactly() -> None:
    for candidate in TRADE_SETUP_CANDIDATES:
        candidate_id = candidate.candidate_id
        assert trade_setup_candidate(candidate_id) == candidate
        assert trade_setup_id_from_box(trade_setup_center(candidate_id)) == candidate_id
        if not candidate.is_no_trade:
            assert candidate.idea is not None
            assert candidate.setup_timeframe is not None
            assert (
                trade_setup_candidate_id(
                    candidate.idea, candidate.setup_timeframe, candidate.direction
                )
                == candidate_id
            )
```

2. [test fixture: `test_candidate_ids_and_semantics_round_trip_for_the_full_catalog`](../../../../tests/unit/decisioning/test_trade_setup_contract.py#L24)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert TRADE_SETUP_CATEGORY_COUNT == len(TRADE_SETUP_CANDIDATES) == 109
    assert trade_setup_candidate(NO_TRADE_ID).is_no_trade

    for candidate_id, candidate in enumerate(TRADE_SETUP_CANDIDATES):
        assert candidate.candidate_id == candidate_id
        assert trade_setup_id_from_box(trade_setup_center(candidate_id)) == candidate_id
        if candidate.is_no_trade:
            continue
        assert candidate.idea is not None
        assert candidate.setup_timeframe is not None
        assert (
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `trade_setup_id_from_box`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Decode a finite normalized Box value to its stable category.

**Exact API:** {py:obj}`decisioning.trade_setup.trade_setup_id_from_box` · **Source:** [decisioning/trade_setup.py:218](../../../../decisioning/trade_setup.py#L218)

**Inputs and outputs:**

- **Args:**

  ```text
  value: Value to process.
  ```

- **Returns:**

  ```text
  Numeric result returned by ``trade_setup_id_from_box``.
  ```

**Observed usage:**

1. [test fixture: `test_trade_setup_ids_and_box_centers_round_trip_exactly`](../../../../tests/integration/test_trade_setup.py#L53)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trade_setup_ids_and_box_centers_round_trip_exactly() -> None:
    for candidate in TRADE_SETUP_CANDIDATES:
        candidate_id = candidate.candidate_id
        assert trade_setup_candidate(candidate_id) == candidate
        assert trade_setup_id_from_box(trade_setup_center(candidate_id)) == candidate_id
        if not candidate.is_no_trade:
            assert candidate.idea is not None
            assert candidate.setup_timeframe is not None
            assert (
                trade_setup_candidate_id(
                    candidate.idea, candidate.setup_timeframe, candidate.direction
                )
                == candidate_id
            )
```

2. [test fixture: `test_trade_setup_box_decoder_rejects_invalid_values`](../../../../tests/integration/test_trade_setup.py#L94)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trade_setup_box_decoder_rejects_invalid_values(value: float) -> None:
    with pytest.raises(ValueError):
        trade_setup_id_from_box(value)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `trade_setup_observation_schema`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Describe the canonical eligibility mask recorded by new checkpoints.

**Exact API:** {py:obj}`decisioning.trade_setup.trade_setup_observation_schema` · **Source:** [decisioning/trade_setup.py:236](../../../../decisioning/trade_setup.py#L236)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``object`` values.
  ```

**Observed usage:**

1. [test fixture: `test_action_and_observation_schemas_use_canonical_coordinates`](../../../../tests/unit/decisioning/test_trade_setup_contract.py#L61)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "exit",
    )
    assert action_schema.indices["trade_setup"] == 0
    assert action_schema.to_dict()["kind"] == "trade_setup_overlay"
    assert action_schema.to_dict()["has_trade_setup"] is True
    assert trade_setup_observation_schema()["mask_key"] == "trade_setup_mask"
```

2. [test fixture: `__init__`](../../../../tests/unit/models/test_mtf_encoder_registration.py#L65)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        self.observation_space = spaces.Dict(schema)
        self.action_space = spaces.Box(-1.0, 1.0, (5,), dtype=np.float32)
        self.action_schema = build_trade_setup_action_schema()
        self.trade_setup_actions = True
        self.strategy_actions = True
        self.trade_setup_observation_schema = trade_setup_observation_schema()
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `validate_trade_setup_observation_schema`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Reject checkpoints whose setup eligibility semantics differ from config.

**Exact API:** {py:obj}`decisioning.trade_setup.validate_trade_setup_observation_schema` · **Source:** [decisioning/trade_setup.py:252](../../../../decisioning/trade_setup.py#L252)

**Inputs and outputs:**

- **Args:**

  ```text
  actual_schema: Actual schema used by the operation described above.
  expected_schema: Key-value data used for the expected schema.
  ```

**Observed usage:**

1. [test fixture: `test_trade_setup_observation_schema_is_checkpoint_checked`](../../../../tests/unit/models/test_trade_setup_observation_schema.py#L20)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trade_setup_observation_schema_is_checkpoint_checked() -> None:
    expected = trade_setup_observation_schema()
    model = SimpleNamespace(_trade_setup_observation_schema=expected)
    validate_trade_setup_observation_schema(model._trade_setup_observation_schema, expected)
    validate_trade_setup_observation_schema(None, None)

    with pytest.raises(ValueError, match="trade setup observation schema"):
        validate_trade_setup_observation_schema(None, expected)
    with pytest.raises(ValueError, match="trade setup observation schema"):
        validate_trade_setup_observation_schema(model._trade_setup_observation_schema, None)
```

2. [production caller: `validate_model_trade_setup_observation_schema`](../../../../learning/rl/agent.py#L319)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def validate_model_trade_setup_observation_schema(
    model: Any, expected_schema: dict[str, Any] | None
) -> None:
    actual = getattr(model, "_trade_setup_observation_schema", None)
    validate_trade_setup_observation_schema(actual, expected_schema)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `TradeSetupActionSchema.indices`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Map each action-coordinate name to its ordered index.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupActionSchema.indices` · **Source:** [decisioning/trade_setup.py:65](../../../../decisioning/trade_setup.py#L65)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``int`` values.
  ```

**Observed usage:**

1. [test fixture: `test_action_and_observation_schemas_use_canonical_coordinates`](../../../../tests/unit/decisioning/test_trade_setup_contract.py#L58)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "tp_mode",
        "z1",
        "z2",
        "exit",
    )
    assert action_schema.indices["trade_setup"] == 0
    assert action_schema.to_dict()["kind"] == "trade_setup_overlay"
    assert action_schema.to_dict()["has_trade_setup"] is True
    assert trade_setup_observation_schema()["mask_key"] == "trade_setup_mask"
```

2. [test fixture: `test_action_schema_has_one_setup_coordinate_and_full_category_catalog`](../../../../tests/unit/models/test_trade_setup_observation_schema.py#L49)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_action_schema_has_one_setup_coordinate_and_full_category_catalog() -> None:
    assert TRADE_SETUP_CATEGORY_COUNT == len(TRADE_SETUP_CANDIDATES) == 109
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_multi_tp=True, has_simplex=True)
    assert schema.names.count("trade_setup") == 1
    assert schema.names[0] == "trade_setup"
    assert schema.indices["trade_setup"] == 0
    assert schema.to_dict()["trade_setup_category_count"] == TRADE_SETUP_CATEGORY_COUNT
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `TradeSetupActionSchema.key`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Return the canonical key for the configured coordinate flags.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupActionSchema.key` · **Source:** [decisioning/trade_setup.py:77](../../../../decisioning/trade_setup.py#L77)

**Inputs and outputs:**

- **Returns:**

  ```text
  Text returned by ``key``.
  ```

**Observed usage:**

1. [production caller: `to_dict`](../../../../decisioning/trade_setup.py#L94)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
        return {
            "kind": "trade_setup_overlay",
            "version": self.version,
            "key": self.key,
            "width": self.width,
            "coordinates": list(self.names),
            "categorical_coordinates": [
                name for name in ("trade_setup", "sl_mode", "tp_mode", "exit") if name in self.names
            ],
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `TradeSetupActionSchema.to_dict`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Return the versioned action contract as JSON-compatible data.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupActionSchema.to_dict` · **Source:** [decisioning/trade_setup.py:85](../../../../decisioning/trade_setup.py#L85)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``object`` values.
  ```

**Observed usage:**

1. [test fixture: `test_trade_setup_action_schema_uses_canonical_coordinate_order`](../../../../tests/integration/test_trade_setup.py#L88)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "z1",
        "z2",
        "exit",
    )
    assert schema.width == 11
    assert schema.to_dict()["trade_setup_category_count"] == TRADE_SETUP_CATEGORY_COUNT
```

2. [test fixture: `test_action_and_observation_schemas_use_canonical_coordinates`](../../../../tests/unit/decisioning/test_trade_setup_contract.py#L59)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "z1",
        "z2",
        "exit",
    )
    assert action_schema.indices["trade_setup"] == 0
    assert action_schema.to_dict()["kind"] == "trade_setup_overlay"
    assert action_schema.to_dict()["has_trade_setup"] is True
    assert trade_setup_observation_schema()["mask_key"] == "trade_setup_mask"
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `TradeSetupActionSchema.width`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Return the number of action coordinates.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupActionSchema.width` · **Source:** [decisioning/trade_setup.py:56](../../../../decisioning/trade_setup.py#L56)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``width``.
  ```

**Observed usage:**

1. [test fixture: `test_trade_setup_action_schema_uses_canonical_coordinate_order`](../../../../tests/integration/test_trade_setup.py#L87)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "tp_mode",
        "z1",
        "z2",
        "exit",
    )
    assert schema.width == 11
    assert schema.to_dict()["trade_setup_category_count"] == TRADE_SETUP_CATEGORY_COUNT
```

2. [test fixture: `test_canonical_distribution_resolves_matching_policy_and_mask`](../../../../tests/unit/simulation/test_environment/test_trade_setup_factory_config.py#L150)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        {"trade_setup_mask": spaces.Box(0.0, 1.0, (TRADE_SETUP_CATEGORY_COUNT,), dtype=np.float32)}
    )
    policy, kwargs, _ = _ppo_policy_and_ent_coef(
        config,
        {},
        spaces.Box(-1.0, 1.0, (schema.width,), dtype=np.float32),
        schema,
        observation_space,
    )

    expected_policy = (
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `TradeSetupCandidate.is_no_trade`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Return whether this candidate represents the no-trade choice.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupCandidate.is_no_trade` · **Source:** [decisioning/trade_setup.py:35](../../../../decisioning/trade_setup.py#L35)

**Inputs and outputs:**

- **Returns:**

  ```text
  Whether is no trade meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_candidate_ids_and_semantics_round_trip_for_the_full_catalog`](../../../../tests/unit/decisioning/test_trade_setup_contract.py#L20)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_candidate_ids_and_semantics_round_trip_for_the_full_catalog() -> None:
    assert TRADE_SETUP_CATEGORY_COUNT == len(TRADE_SETUP_CANDIDATES) == 109
    assert trade_setup_candidate(NO_TRADE_ID).is_no_trade

    for candidate_id, candidate in enumerate(TRADE_SETUP_CANDIDATES):
        assert candidate.candidate_id == candidate_id
        assert trade_setup_id_from_box(trade_setup_center(candidate_id)) == candidate_id
        if candidate.is_no_trade:
# … caller assertions omitted …
```

2. [tutorial example: `trade_setup_policy · code cell 2`](../../../../docs/learn/tutorials/advanced/trade_setup_policy.ipynb)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
from collections import Counter

from decisioning.trade_setup import (
    NO_TRADE_ID,
    TRADE_SETUP_CATEGORY_COUNT,
    TRADE_SETUP_IDEAS,
    TRADE_SETUP_TIMEFRAMES,
    trade_setup_candidate,
    trade_setup_candidate_id,
    trade_setup_center,
)

print(
    "categories:",
    TRADE_SETUP_CATEGORY_COUNT,
    "ideas:",
    TRADE_SETUP_IDEAS,
    "timeframes:",
    TRADE_SETUP_TIMEFRAMES,
)
no_trade = trade_setup_candidate(NO_TRADE_ID)
po3_h1_long_id = trade_setup_candidate_id("po3", "H1", 1)
po3_h1_long = trade_setup_candidate(po3_h1_long_id)
print("no trade:", no_trade)
print("PO3 H1 long:", po3_h1_long, "box center:", round(trade_setup_center(po3_h1_long_id), 4))
assert TRADE_SETUP_CATEGORY_COUNT == 109
assert no_trade.is_no_trade
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`
