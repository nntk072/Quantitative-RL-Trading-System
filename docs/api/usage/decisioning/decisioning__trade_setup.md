# Decisioning · `trade_setup`

This page contains 23 public callable records owned by `decisioning.trade_setup`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TradeSetupActionSchema`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Versioned Box action layout whose first coordinate selects a setup.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupActionSchema` · **Source:** [decisioning/trade_setup.py:187](../../../../decisioning/trade_setup.py#L187)

**Observed usage:**

1. [production caller: `build_trade_setup_action_schema`](../../../../decisioning/trade_setup.py#L308)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    if has_simplex:
        coordinates.extend(("z1", "z2"))
    if has_entry_execution:
        coordinates.extend(("entry_execution", "limit_offset_atr", "limit_ttl_bars"))
    coordinates.append("exit")
    return TradeSetupActionSchema(
        names=tuple(coordinates),
        has_sl_mode=has_sl_mode,
        has_tp_mode=has_tp_mode,
        has_multi_tp=has_multi_tp,
        has_simplex=has_simplex,
        has_entry_execution=has_entry_execution,
        version=(
            TRADE_SETUP_EXECUTION_ACTION_VERSION
            if has_entry_execution
            else TRADE_SETUP_ACTION_VERSION
        ),
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `TradeSetupCandidate`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** One stable policy choice: idea, setup timeframe, direction, or no-trade.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupCandidate` · **Source:** [decisioning/trade_setup.py:142](../../../../decisioning/trade_setup.py#L142)

**Observed usage:**

1. [production caller: `_catalog`](../../../../decisioning/trade_setup.py#L471)

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

## `TradeSetupExecutionChoice`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Decoded market/limit choice and its conditional limit controls.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupExecutionChoice` · **Source:** [decisioning/trade_setup.py:161](../../../../decisioning/trade_setup.py#L161)

**Observed usage:**

1. [production caller: `decode_trade_setup_execution_choice`](../../../../decisioning/trade_setup.py#L365)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    order_type = "market" if values[indices["entry_execution"]] < 0.0 else "limit"
    unit_offset = 0.5 * (values[indices["limit_offset_atr"]] + 1.0)
    unit_ttl = 0.5 * (values[indices["limit_ttl_bars"]] + 1.0)
    max_ttl = int(max_limit_ttl_bars)
    ttl_bars = 1 + min(int(unit_ttl * max_ttl), max_ttl - 1)
    return TradeSetupExecutionChoice(
        order_type=order_type,
        limit_offset_atr=unit_offset * float(max_limit_offset_atr),
        ttl_bars=ttl_bars,
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `TradeSetupGeometryChoice`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Decoded stop/target geometry and position-management coordinates.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupGeometryChoice` · **Source:** [decisioning/trade_setup.py:170](../../../../decisioning/trade_setup.py#L170)

**Observed usage:**

1. [production caller: `decode_trade_setup_geometry_choice`](../../../../decisioning/trade_setup.py#L450)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            to_unit(indices["tp_mode"]), default_tp_mode, tp_mode_defer_threshold
        )
        if schema.has_tp_mode
        else (default_tp_mode, False)
    )
    return TradeSetupGeometryChoice(
        stop_anchor_fraction=float(stop_fraction),
        target_fraction=float(target_fraction),
        target_selections=target_selections,
        simplex_logits=simplex_logits,
        exit_mode=exit_mode,
        sl_mode=sl_mode,
        sl_mode_explicit=sl_mode_explicit,
        has_sl_mode=schema.has_sl_mode,
        tp_mode=tp_mode,
        tp_mode_explicit=tp_mode_explicit,
        has_tp_mode=schema.has_tp_mode,
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `build_trade_setup_action_schema`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Create the versioned action layout for primary trade-setup selection.

**Exact API:** {py:obj}`decisioning.trade_setup.build_trade_setup_action_schema` · **Source:** [decisioning/trade_setup.py:275](../../../../decisioning/trade_setup.py#L275)

**Inputs and outputs:**

- **Args:**

  ```text
  has_sl_mode: Whether to enable or require the has sl mode.
  has_tp_mode: Whether to enable or require the has tp mode.
  has_multi_tp: Whether to enable or require the has multi tp.
  has_simplex: Whether to enable or require the has simplex.
  has_entry_execution: Whether the policy chooses market or limit entry.
  ```

- **Returns:**

  ```text
  Result of create the versioned action layout for primary trade-setup selection.
  ```

**Observed usage:**

1. [test fixture: `_backtest_inputs`](../../../../tests/integration/backtest/test_agent_selected_entry_execution.py#L104)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    features.loc[index[1:], "entry_idea_fvg_retest_M1_long"] = 1.0
    features.loc[index[1:], "fvg_bull_active"] = 1.0
    features.loc[index[1:], "fvg_bull_retest_confirmed_at_time_ns"] = index[1].value
    features.loc[index[1:], "fvg_bull_retest_origin_time_ns"] = index[0].value
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_entry_execution=True)
    choice = _action(schema, candidate_id=candidate_id, limit=True)
    return (
        bars,
        features,
        TickBook(np.array([], dtype=np.int64), np.array([]), np.array([])),
# … caller assertions omitted …
```

2. [test fixture: `test_trading_env_episode_end_cancellation_preserves_limit_setup_identity`](../../../../tests/integration/backtest/test_agent_selected_entry_execution.py#L356)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trading_env_episode_end_cancellation_preserves_limit_setup_identity() -> None:
    bars, features, tickbook, _, candidate_id, _ = _backtest_inputs()
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_entry_execution=True)
    action = _action(schema, candidate_id=candidate_id, limit=True)
    env = TradingEnv(
        bars=bars,
        features=features,
        obs_window=1,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `candidate_geometry_observation_schema`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Describe the versioned fixed-width candidate geometry observations.

**Exact API:** {py:obj}`decisioning.trade_setup.candidate_geometry_observation_schema` · **Source:** [decisioning/trade_setup.py:103](../../../../decisioning/trade_setup.py#L103)

**Inputs and outputs:**

- **Returns:**

  ```text
  Schema fields for candidate IDs, features, eligibility mask, and entry types.
  ```

**Observed usage:**

1. [test fixture: `test_candidate_geometry_observation_schema_versions_fixed_slot_contract`](../../../../tests/unit/decisioning/test_candidate_geometry_contract.py#L36)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_candidate_geometry_observation_schema_versions_fixed_slot_contract() -> None:
    schema = candidate_geometry_observation_schema()
    assert schema["candidate_count"] == 217
    assert schema["feature_names"] == list(CANDIDATE_GEOMETRY_FEATURE_NAMES)
    assert schema["no_trade_slot"] == 0
    assert schema["candidate_ids_key"] == "candidate_ids"
    assert schema["candidate_features_key"] == "candidate_features"
    assert schema["candidate_mask_key"] == "candidate_mask"
```

2. [test fixture: `test_candidate_geometry_observation_schema_round_trip_and_mismatch`](../../../../tests/unit/decisioning/test_candidate_geometry_schema_validation.py#L12)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_candidate_geometry_observation_schema_round_trip_and_mismatch() -> None:
    expected = candidate_geometry_observation_schema()
    validate_candidate_geometry_observation_schema(expected, expected)

    mutated = dict(expected)
    candidate_count = expected["candidate_count"]
    assert isinstance(candidate_count, int)
    mutated["candidate_count"] = candidate_count - 1
    with pytest.raises(ValueError, match="candidate geometry observation schema"):
        validate_candidate_geometry_observation_schema(mutated, expected)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `candidate_geometry_slot`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Return the stable candidate slot for a setup and entry type.

**Exact API:** {py:obj}`decisioning.trade_setup.candidate_geometry_slot` · **Source:** [decisioning/trade_setup.py:48](../../../../decisioning/trade_setup.py#L48)

**Inputs and outputs:**

- **Args:**

  ```text
  candidate_id: Nonzero executable setup identifier.
  entry_type: Entry hypothesis, either ``market`` or ``limit``.
  ```

- **Returns:**

  ```text
  Stable action slot for the setup and entry-type pair.
  ```

**Observed usage:**

1. [test fixture: `test_candidate_geometry_slots_round_trip_the_full_setup_entry_pair`](../../../../tests/unit/decisioning/test_candidate_geometry_contract.py#L20)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_candidate_geometry_slots_round_trip_the_full_setup_entry_pair() -> None:
    assert candidate_geometry_slot_count() == 217
    assert candidate_geometry_slot_semantics(0) == (0, "market")
    for candidate_id in range(1, 109):
        for entry_type in CANDIDATE_GEOMETRY_ENTRY_TYPES:
            slot = candidate_geometry_slot(candidate_id, entry_type)
            assert candidate_geometry_slot_semantics(slot) == (candidate_id, entry_type)
```

2. [test fixture: `test_candidate_geometry_rejects_invalid_candidate_slot_inputs`](../../../../tests/unit/decisioning/test_candidate_geometry_contract.py#L32)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_candidate_geometry_rejects_invalid_candidate_slot_inputs(
    candidate_id: int | float, entry_type: str
) -> None:
    with pytest.raises(ValueError):
        candidate_geometry_slot(candidate_id, entry_type)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `candidate_geometry_slot_count`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Return the fixed slot count including no-trade and entry hypotheses.

**Exact API:** {py:obj}`decisioning.trade_setup.candidate_geometry_slot_count` · **Source:** [decisioning/trade_setup.py:75](../../../../decisioning/trade_setup.py#L75)

**Inputs and outputs:**

- **Returns:**

  ```text
  Total action slots across no-trade and all setup-entry combinations.
  ```

**Observed usage:**

1. [test fixture: `test_candidate_geometry_slots_round_trip_the_full_setup_entry_pair`](../../../../tests/unit/decisioning/test_candidate_geometry_contract.py#L16)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_candidate_geometry_slots_round_trip_the_full_setup_entry_pair() -> None:
    assert candidate_geometry_slot_count() == 217
    assert candidate_geometry_slot_semantics(0) == (0, "market")
    for candidate_id in range(1, 109):
        for entry_type in CANDIDATE_GEOMETRY_ENTRY_TYPES:
            slot = candidate_geometry_slot(candidate_id, entry_type)
            assert candidate_geometry_slot_semantics(slot) == (candidate_id, entry_type)
```

2. [test fixture: `test_candidate_geometry_trace_records_selected_slot_snapshot_and_decoded_action`](../../../../tests/unit/evaluation/test_rollout.py#L123)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        candidate_geometry_slot_semantics,
    )

    selected_id = 5
    slot = candidate_geometry_slot(selected_id, "limit")
    count = candidate_geometry_slot_count()
    candidate_ids = np.asarray(
        [candidate_geometry_slot_semantics(index)[0] for index in range(count)],
        dtype=np.int64,
    )
    features = np.zeros((count, len(CANDIDATE_GEOMETRY_FEATURE_NAMES)), dtype=np.float32)
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `candidate_geometry_slot_semantics`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Decode a nonzero candidate slot to its setup ID and entry type.

**Exact API:** {py:obj}`decisioning.trade_setup.candidate_geometry_slot_semantics` · **Source:** [decisioning/trade_setup.py:85](../../../../decisioning/trade_setup.py#L85)

**Inputs and outputs:**

- **Args:**

  ```text
  slot: Candidate-geometry action slot to decode.
  ```

- **Returns:**

  ```text
  Setup identifier and entry type; slot zero maps to no-trade.
  ```

**Observed usage:**

1. [test fixture: `test_candidate_geometry_slots_round_trip_the_full_setup_entry_pair`](../../../../tests/unit/decisioning/test_candidate_geometry_contract.py#L17)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_candidate_geometry_slots_round_trip_the_full_setup_entry_pair() -> None:
    assert candidate_geometry_slot_count() == 217
    assert candidate_geometry_slot_semantics(0) == (0, "market")
    for candidate_id in range(1, 109):
        for entry_type in CANDIDATE_GEOMETRY_ENTRY_TYPES:
            slot = candidate_geometry_slot(candidate_id, entry_type)
            assert candidate_geometry_slot_semantics(slot) == (candidate_id, entry_type)
```

2. [test fixture: `test_candidate_geometry_trace_records_selected_slot_snapshot_and_decoded_action`](../../../../tests/unit/evaluation/test_rollout.py#L125)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    selected_id = 5
    slot = candidate_geometry_slot(selected_id, "limit")
    count = candidate_geometry_slot_count()
    candidate_ids = np.asarray(
        [candidate_geometry_slot_semantics(index)[0] for index in range(count)],
        dtype=np.int64,
    )
    features = np.zeros((count, len(CANDIDATE_GEOMETRY_FEATURE_NAMES)), dtype=np.float32)
    features[slot] = np.arange(len(CANDIDATE_GEOMETRY_FEATURE_NAMES), dtype=np.float32) + 0.5
    mask = np.zeros(count, dtype=np.bool_)
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `decode_trade_setup_execution_choice`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Decode policy coordinates into an order type, ATR offset, and TTL.

**Exact API:** {py:obj}`decisioning.trade_setup.decode_trade_setup_execution_choice` · **Source:** [decisioning/trade_setup.py:323](../../../../decisioning/trade_setup.py#L323)

**Inputs and outputs:**

- **Args:**

  ```text
  action: Policy action coordinates in schema order.
  schema: Action schema that defines coordinate positions and width.
  max_limit_offset_atr: Largest available limit offset in ATR units.
  max_limit_ttl_bars: Largest allowed order lifetime in M1 bars.
  ```

- **Returns:**

  ```text
  Chosen order type, ATR offset, and integer TTL.
  ```

**Observed usage:**

1. [test fixture: `test_entry_execution_action_decodes_market_and_conditional_limit_controls`](../../../../tests/unit/decisioning/test_trade_setup_contract.py#L106)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    indices = schema.indices
    action[indices["entry_execution"]] = -0.01
    action[indices["limit_offset_atr"]] = 1.0
    action[indices["limit_ttl_bars"]] = -1.0

    market = decode_trade_setup_execution_choice(
        action,
        schema,
        max_limit_offset_atr=1.5,
        max_limit_ttl_bars=60,
    )

    assert market.order_type == "market"
    assert market.limit_offset_atr == pytest.approx(1.5)
    assert market.ttl_bars == 1

# … caller assertions omitted …
```

2. [test fixture: `test_entry_execution_decoder_rejects_invalid_bounds`](../../../../tests/unit/decisioning/test_trade_setup_contract.py#L139)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_entry_execution_decoder_rejects_invalid_bounds(offset: float, ttl: int) -> None:
    schema = build_trade_setup_action_schema(has_entry_execution=True)
    with pytest.raises(ValueError):
        decode_trade_setup_execution_choice(
            [0.0] * schema.width,
            schema,
            max_limit_offset_atr=offset,
            max_limit_ttl_bars=ttl,
        )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `decode_trade_setup_geometry_choice`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Decode the setup action's stop, target, and exit coordinates.

**Exact API:** {py:obj}`decisioning.trade_setup.decode_trade_setup_geometry_choice` · **Source:** [decisioning/trade_setup.py:372](../../../../decisioning/trade_setup.py#L372)

**Inputs and outputs:**

- **Args:**

  ```text
  action: Policy action coordinates in schema order.
  schema: Action schema that defines coordinate positions and features.
  allow_ema_exit: Whether the policy can select EMA-based exits.
  default_sl_mode: Stop mode used when the policy defers its choice.
  default_tp_mode: Target mode used when the policy defers its choice.
  sl_mode_defer_threshold: Center-band width that defers the stop-mode choice.
  tp_mode_defer_threshold: Center-band width that defers the target-mode choice.
  ```

- **Returns:**

  ```text
  Decoded stop, target, exit, and management-mode settings.
  ```

**Observed usage:**

1. [test fixture: `test_setup_geometry_decoder_maps_stop_target_and_exit_coordinates`](../../../../tests/unit/decisioning/test_trade_setup_contract.py#L154)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    action = [0.0] * schema.width
    action[schema.indices["stop"]] = -0.5
    action[schema.indices["target"]] = 0.6
    action[schema.indices["exit"]] = -0.6

    choice = decode_trade_setup_geometry_choice(action, schema)

    assert choice.stop_anchor_fraction == pytest.approx(0.5)
    assert choice.target_fraction == pytest.approx(0.8)
    assert choice.target_selections is None
    assert choice.simplex_logits is None
# … caller assertions omitted …
```

2. [test fixture: `test_setup_geometry_decoder_preserves_multi_target_slots_and_simplex_inputs`](../../../../tests/unit/decisioning/test_trade_setup_contract.py#L183)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "z1": -0.25,
        "z2": 0.5,
    }.items():
        action[schema.indices[name]] = value

    choice = decode_trade_setup_geometry_choice(action, schema)

    assert choice.stop_anchor_fraction == pytest.approx(0.0)
    assert choice.target_fraction == pytest.approx(0.875)
    assert choice.target_selections == pytest.approx((0.25, 0.5, 0.875))
    assert choice.simplex_logits == pytest.approx((0.375, 0.75))
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `trade_setup_candidate`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Return a setup entry by ID, rejecting unknown IDs.

**Exact API:** {py:obj}`decisioning.trade_setup.trade_setup_candidate` · **Source:** [decisioning/trade_setup.py:486](../../../../decisioning/trade_setup.py#L486)

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

1. [test fixture: `test_strategy_order_uses_setup_floor_for_stops_and_all_timeframes_for_targets`](../../../../tests/integration/backtest/test_entry_levels.py#L333)

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

2. [test fixture: `test_standard_deviation_trade_setup_uses_its_own_timeframe_level_one_stop`](../../../../tests/integration/backtest/test_entry_levels.py#L371)

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

**Exact API:** {py:obj}`decisioning.trade_setup.trade_setup_candidate_id` · **Source:** [decisioning/trade_setup.py:502](../../../../decisioning/trade_setup.py#L502)

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

1. [test fixture: `_backtest_inputs`](../../../../tests/integration/backtest/test_agent_selected_entry_execution.py#L99)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        0.0,
        index=index,
        columns=[name for _, name in trade_setup_candidate_feature_columns()],
    )
    features["atr_5"] = 1.0
    candidate_id = trade_setup_candidate_id("fvg_retest", "M1", 1)
    features.loc[index[1:], "entry_idea_fvg_retest_M1_long"] = 1.0
    features.loc[index[1:], "fvg_bull_active"] = 1.0
    features.loc[index[1:], "fvg_bull_retest_confirmed_at_time_ns"] = index[1].value
    features.loc[index[1:], "fvg_bull_retest_origin_time_ns"] = index[0].value
    schema = build_trade_setup_action_schema(has_sl_mode=True, has_entry_execution=True)
# … caller assertions omitted …
```

2. [test fixture: `test_event_backtest_ifvg_limit_follows_zone_lifetime_after_retest_pulse`](../../../../tests/integration/backtest/test_agent_selected_entry_execution.py#L401)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    zone_change: str,
    expected_cancel_reason: str | None,
) -> None:
    bars, features, _, schema, _, _ = _backtest_inputs()
    index = bars.index
    candidate_id = trade_setup_candidate_id("ifvg_retest", "M1", 1)
    features["entry_idea_fvg_retest_M1_long"] = 0.0
    features["entry_idea_ifvg_retest_M1_long"] = 0.0
    features.loc[index[1], "entry_idea_ifvg_retest_M1_long"] = 1.0
    features["ifvg_bull_active"] = 1.0
    features["ifvg_bull_confirmed_at_time_ns"] = index[0].value
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `trade_setup_center`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Encode an ID at the center of its equal-width Box interval.

**Exact API:** {py:obj}`decisioning.trade_setup.trade_setup_center` · **Source:** [decisioning/trade_setup.py:521](../../../../decisioning/trade_setup.py#L521)

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

1. [test fixture: `_action`](../../../../tests/integration/backtest/test_agent_selected_entry_execution.py#L61)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    candidate_id: int,
    limit: bool,
) -> Array:
    values = np.zeros(schema.width, dtype=np.float32)
    indices = schema.indices
    values[indices["trade_setup"]] = trade_setup_center(candidate_id)
    values[indices["entry_execution"]] = 1.0 if limit else -1.0
    values[indices["limit_offset_atr"]] = -1.0  # at the causal decision close
    values[indices["limit_ttl_bars"]] = -1.0  # one bar
    values[indices["stop"]] = -0.4
    values[indices["target"]] = 0.8
# … caller assertions omitted …
```

2. [test fixture: `execute`](../../../../tests/integration/backtest/test_agent_selected_entry_execution.py#L598)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def execute(require_trade_through: bool):
        selected = False
        no_trade_action = np.zeros(schema.width, dtype=np.float32)
        no_trade_action[schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)
        no_trade_action[schema.indices["entry_execution"]] = -1.0

        def policy(observation: Any) -> Array:
            nonlocal selected
            mask = np.asarray(observation["trade_setup_mask"])
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `trade_setup_id_from_box`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Decode a finite normalized Box value to its stable category.

**Exact API:** {py:obj}`decisioning.trade_setup.trade_setup_id_from_box` · **Source:** [decisioning/trade_setup.py:534](../../../../decisioning/trade_setup.py#L534)

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

1. [test fixture: `test_random_setup_baseline_uses_shared_rollout_decision_trace`](../../../../tests/integration/evaluation/test_random_eligible_setup_rollout.py#L127)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert decisions["selected_timeframe"].eq("M5").all()
    assert decisions["selected_direction"].eq(1).all()
    assert decisions["action_trade_setup"].notna().all()
    assert decisions.apply(
        lambda row: (
            trade_setup_id_from_box(float(row["action_trade_setup"]))
            == int(row["trade_setup_candidate_id"])
        ),
        axis=1,
    ).all()

# … caller assertions omitted …
```

2. [test fixture: `test_trade_setup_ids_and_box_centers_round_trip_exactly`](../../../../tests/integration/test_trade_setup.py#L53)

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

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `trade_setup_observation_schema`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Describe the canonical eligibility mask recorded by new checkpoints.

**Exact API:** {py:obj}`decisioning.trade_setup.trade_setup_observation_schema` · **Source:** [decisioning/trade_setup.py:552](../../../../decisioning/trade_setup.py#L552)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``object`` values.
  ```

**Observed usage:**

1. [test fixture: `test_action_and_observation_schemas_use_canonical_coordinates`](../../../../tests/unit/decisioning/test_trade_setup_contract.py#L64)

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

2. [test fixture: `__init__`](../../../../tests/unit/learning/test_candidate_geometry_agent.py#L65)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        )
        self.action_space = spaces.Box(-1.0, 1.0, (self.action_schema.width,), dtype=np.float32)
        self.trade_setup_actions = True
        self.candidate_geometry_actions = True
        self.strategy_actions = True
        self.trade_setup_observation_schema = trade_setup_observation_schema()
        self.candidate_geometry_observation_schema = candidate_geometry_observation_schema()
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `validate_candidate_geometry_observation_schema`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Reject checkpoints whose price-aware candidate tensor semantics differ.

**Exact API:** {py:obj}`decisioning.trade_setup.validate_candidate_geometry_observation_schema` · **Source:** [decisioning/trade_setup.py:583](../../../../decisioning/trade_setup.py#L583)

**Inputs and outputs:**

- **Args:**

  ```text
  actual_schema: Candidate-geometry schema recorded on the checkpoint.
  expected_schema: Candidate-geometry schema required by the configured environment.
  ```

**Observed usage:**

1. [test fixture: `test_candidate_geometry_observation_schema_round_trip_and_mismatch`](../../../../tests/unit/decisioning/test_candidate_geometry_schema_validation.py#L13)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_candidate_geometry_observation_schema_round_trip_and_mismatch() -> None:
    expected = candidate_geometry_observation_schema()
    validate_candidate_geometry_observation_schema(expected, expected)

    mutated = dict(expected)
    candidate_count = expected["candidate_count"]
    assert isinstance(candidate_count, int)
    mutated["candidate_count"] = candidate_count - 1
    with pytest.raises(ValueError, match="candidate geometry observation schema"):
        validate_candidate_geometry_observation_schema(mutated, expected)
```

2. [test fixture: `test_candidate_geometry_schema_is_absent_for_non_price_aware_checkpoint`](../../../../tests/unit/decisioning/test_candidate_geometry_schema_validation.py#L24)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_candidate_geometry_schema_is_absent_for_non_price_aware_checkpoint() -> None:
    validate_candidate_geometry_observation_schema(None, None)
    with pytest.raises(ValueError, match="candidate geometry observation schema"):
        validate_candidate_geometry_observation_schema(
            None, candidate_geometry_observation_schema()
        )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `validate_trade_setup_observation_schema`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Reject checkpoints whose setup eligibility semantics differ from config.

**Exact API:** {py:obj}`decisioning.trade_setup.validate_trade_setup_observation_schema` · **Source:** [decisioning/trade_setup.py:568](../../../../decisioning/trade_setup.py#L568)

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

2. [production caller: `validate_model_trade_setup_observation_schema`](../../../../learning/rl/agent.py#L321)

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

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupActionSchema.indices` · **Source:** [decisioning/trade_setup.py:208](../../../../decisioning/trade_setup.py#L208)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``int`` values.
  ```

**Observed usage:**

1. [test fixture: `_action`](../../../../tests/integration/backtest/test_agent_selected_entry_execution.py#L60)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    *,
    candidate_id: int,
    limit: bool,
) -> Array:
    values = np.zeros(schema.width, dtype=np.float32)
    indices = schema.indices
    values[indices["trade_setup"]] = trade_setup_center(candidate_id)
    values[indices["entry_execution"]] = 1.0 if limit else -1.0
    values[indices["limit_offset_atr"]] = -1.0  # at the causal decision close
    values[indices["limit_ttl_bars"]] = -1.0  # one bar
    values[indices["stop"]] = -0.4
# … caller assertions omitted …
```

2. [test fixture: `execute`](../../../../tests/integration/backtest/test_agent_selected_entry_execution.py#L598)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def execute(require_trade_through: bool):
        selected = False
        no_trade_action = np.zeros(schema.width, dtype=np.float32)
        no_trade_action[schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)
        no_trade_action[schema.indices["entry_execution"]] = -1.0

        def policy(observation: Any) -> Array:
            nonlocal selected
            mask = np.asarray(observation["trade_setup_mask"])
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `TradeSetupActionSchema.key`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Return the canonical key for the configured coordinate flags.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupActionSchema.key` · **Source:** [decisioning/trade_setup.py:220](../../../../decisioning/trade_setup.py#L220)

**Inputs and outputs:**

- **Returns:**

  ```text
  Text returned by ``key``.
  ```

**Observed usage:**

1. [production caller: `to_dict`](../../../../decisioning/trade_setup.py#L237)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
        return {
            "kind": "trade_setup_overlay",
            "version": self.version,
            "key": self.key,
            "width": self.width,
            "coordinates": list(self.names),
            "categorical_coordinates": [
                name
                for name in ("trade_setup", "sl_mode", "tp_mode", "entry_execution", "exit")
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `TradeSetupActionSchema.to_dict`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Return the versioned action contract as JSON-compatible data.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupActionSchema.to_dict` · **Source:** [decisioning/trade_setup.py:228](../../../../decisioning/trade_setup.py#L228)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``object`` values.
  ```

**Observed usage:**

1. [test fixture: `test_matched_runner_accepts_deterministic_structure_rule_without_checkpoint`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L322)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    result = outputs["priority_fvg"]
    expected_candidate = trade_setup_candidate_id("fvg_retest", "M5", 1)

    assert result["policy_metadata"]["policy_source"] == "deterministic_rule"
    assert result["policy_metadata"]["policy_id"] == "structure_priority_setup_v1"
    assert result["policy_metadata"]["action_schema"] == schema.to_dict()
    assert result["policy_metadata"]["risk_sizing"]["policy_risk_coordinate_is_constant"] is True
    assert set(result["decisions"]["trade_setup_candidate_id"]) == {expected_candidate}

    bundle_path = write_matched_setup_baseline_bundle(
        outputs,
# … caller assertions omitted …
```

2. [test fixture: `test_tier0_baselines_record_dollar_band_budget_and_fixed_coordinate`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L434)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                    "checkpoint_source_key": "checkpoint",
                    "training_seed": 3,
                    "training_total_steps": 10,
                    "policy_action_mode": "stochastic",
                    "policy_action_seed": 9,
                    "action_schema": action_schema.to_dict(),
                },
            )
        },
    )
    assert (
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `TradeSetupActionSchema.width`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Return the number of action coordinates.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupActionSchema.width` · **Source:** [decisioning/trade_setup.py:199](../../../../decisioning/trade_setup.py#L199)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``width``.
  ```

**Observed usage:**

1. [test fixture: `_action`](../../../../tests/integration/backtest/test_agent_selected_entry_execution.py#L59)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    schema: TradeSetupActionSchema,
    *,
    candidate_id: int,
    limit: bool,
) -> Array:
    values = np.zeros(schema.width, dtype=np.float32)
    indices = schema.indices
    values[indices["trade_setup"]] = trade_setup_center(candidate_id)
    values[indices["entry_execution"]] = 1.0 if limit else -1.0
    values[indices["limit_offset_atr"]] = -1.0  # at the causal decision close
    values[indices["limit_ttl_bars"]] = -1.0  # one bar
# … caller assertions omitted …
```

2. [test fixture: `execute`](../../../../tests/integration/backtest/test_agent_selected_entry_execution.py#L597)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def execute(require_trade_through: bool):
        selected = False
        no_trade_action = np.zeros(schema.width, dtype=np.float32)
        no_trade_action[schema.indices["trade_setup"]] = trade_setup_center(NO_TRADE_ID)
        no_trade_action[schema.indices["entry_execution"]] = -1.0

        def policy(observation: Any) -> Array:
            nonlocal selected
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `TradeSetupCandidate.is_no_trade`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.trade_setup`

**Purpose:** Return whether this candidate represents the no-trade choice.

**Exact API:** {py:obj}`decisioning.trade_setup.TradeSetupCandidate.is_no_trade` · **Source:** [decisioning/trade_setup.py:151](../../../../decisioning/trade_setup.py#L151)

**Inputs and outputs:**

- **Returns:**

  ```text
  Whether is no trade meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_candidate_ids_and_semantics_round_trip_for_the_full_catalog`](../../../../tests/unit/decisioning/test_trade_setup_contract.py#L23)

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
