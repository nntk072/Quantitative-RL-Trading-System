# Evaluation · `rollout.structure_priority_setup`

This page contains 7 public callable records owned by `evaluation.rollout.structure_priority_setup`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `StructurePrioritySetupPolicy`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.rollout.structure_priority_setup`

**Purpose:** Select an eligible setup by declared family and timeframe precedence.

**Exact API:** {py:obj}`evaluation.rollout.structure_priority_setup.StructurePrioritySetupPolicy` · **Source:** [evaluation/rollout/structure_priority_setup.py:21](../../../../evaluation/rollout/structure_priority_setup.py#L21)

**Observed usage:**

1. [test fixture: `test_matched_runner_accepts_deterministic_structure_rule_without_checkpoint`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L298)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        has_tp_mode=bool(cfg.env.allow_agent_tp_mode),
        has_multi_tp=bool(cfg.env.allow_multi_tp),
        has_simplex=bool(cfg.env.allow_multi_tp and cfg.env.allow_simplex),
    )
    rule_model = StructurePrioritySetupRolloutModel(
        StructurePrioritySetupPolicy(
            schema,
            idea_priority=("fvg_retest",),
            timeframe_priority=("M5",),
            normalized_risk=0.5,
        )
    )
    outputs = evaluate_tier0_setup_baselines(
        cfg,
        bars,
        features,
# … caller assertions omitted …
```

2. [test fixture: `_policy`](../../../../tests/unit/evaluation/test_structure_priority_setup.py#L30)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _policy() -> StructurePrioritySetupPolicy:
    return StructurePrioritySetupPolicy(
        build_trade_setup_action_schema(),
        idea_priority=("po3", "fvg_retest"),
        timeframe_priority=("M5", "M1"),
        normalized_risk=0.25,
    )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `StructurePrioritySetupRolloutModel`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.rollout.structure_priority_setup`

**Purpose:** Expose the deterministic structure rule through the rollout interface.

**Exact API:** {py:obj}`evaluation.rollout.structure_priority_setup.StructurePrioritySetupRolloutModel` · **Source:** [evaluation/rollout/structure_priority_setup.py:161](../../../../evaluation/rollout/structure_priority_setup.py#L161)

**Observed usage:**

1. [test fixture: `test_matched_runner_accepts_deterministic_structure_rule_without_checkpoint`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L297)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        has_sl_mode=bool(cfg.env.allow_agent_sl_mode),
        has_tp_mode=bool(cfg.env.allow_agent_tp_mode),
        has_multi_tp=bool(cfg.env.allow_multi_tp),
        has_simplex=bool(cfg.env.allow_multi_tp and cfg.env.allow_simplex),
    )
    rule_model = StructurePrioritySetupRolloutModel(
        StructurePrioritySetupPolicy(
            schema,
            idea_priority=("fvg_retest",),
            timeframe_priority=("M5",),
            normalized_risk=0.5,
        )
    )
    outputs = evaluate_tier0_setup_baselines(
        cfg,
        bars,
        features,
        None,
# … caller assertions omitted …
```

2. [test fixture: `test_structure_priority_rollout_model_exposes_schema_and_rule_provenance`](../../../../tests/unit/evaluation/test_structure_priority_setup.py#L89)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_structure_priority_rollout_model_exposes_schema_and_rule_provenance() -> None:
    policy = _policy()
    model = StructurePrioritySetupRolloutModel(policy)
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)

    action, recurrent_state = model.predict(_observation(candidate_id), deterministic=True)
    metadata = model.policy_metadata

# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `StructurePrioritySetupPolicy.metadata`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.rollout.structure_priority_setup`

**Purpose:** Describe the fixed rule and the information it is permitted to use.

**Exact API:** {py:obj}`evaluation.rollout.structure_priority_setup.StructurePrioritySetupPolicy.metadata` · **Source:** [evaluation/rollout/structure_priority_setup.py:130](../../../../evaluation/rollout/structure_priority_setup.py#L130)

**Inputs and outputs:**

- **Returns:**

  ```text
  Provenance metadata for this deterministic baseline policy.
  ```

**Observed usage:**

1. [test fixture: `test_structure_priority_stays_market_only_with_execution_coordinates`](../../../../tests/unit/evaluation/test_structure_priority_setup.py#L125)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )

    assert choice.order_type == "market"
    assert choice.limit_offset_atr == 0.0
    assert choice.ttl_bars == 1
    assert policy.metadata()["entry_execution"] == "market"
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `StructurePrioritySetupRolloutModel.hybrid_action_coordinates`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.rollout.structure_priority_setup`

**Purpose:** Return the action coordinate names expected by the policy.

**Exact API:** {py:obj}`evaluation.rollout.structure_priority_setup.StructurePrioritySetupRolloutModel.hybrid_action_coordinates` · **Source:** [evaluation/rollout/structure_priority_setup.py:182](../../../../evaluation/rollout/structure_priority_setup.py#L182)

**Inputs and outputs:**

- **Returns:**

  ```text
  Ordered names defined by the wrapped action schema.
  ```

**Observed usage:**

1. [test fixture: `test_structure_priority_rollout_model_exposes_schema_and_rule_provenance`](../../../../tests/unit/evaluation/test_structure_priority_setup.py#L97)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    action, recurrent_state = model.predict(_observation(candidate_id), deterministic=True)
    metadata = model.policy_metadata

    assert recurrent_state is None
    assert trade_setup_id_from_box(float(action[0])) == candidate_id
    assert model.hybrid_action_coordinates == policy.action_schema.names
    assert metadata["baseline_tier"] == "tier_1_deterministic_structure_rule"
    assert metadata["permitted_information"] == ["current_observation.trade_setup_mask"]
    assert metadata["training_performed"] is False
    assert metadata["selection_or_tuning_performed"] is False
    assert metadata["risk_coordinate_is_constant"] is True
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `StructurePrioritySetupRolloutModel.policy`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.rollout.structure_priority_setup`

**Purpose:** Return this rollout-compatible model instance.

**Exact API:** {py:obj}`evaluation.rollout.structure_priority_setup.StructurePrioritySetupRolloutModel.policy` · **Source:** [evaluation/rollout/structure_priority_setup.py:173](../../../../evaluation/rollout/structure_priority_setup.py#L173)

**Inputs and outputs:**

- **Returns:**

  ```text
  This model wrapper.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = StructurePrioritySetupRolloutModel(...)
value = instance.policy
```

**Lifecycle context:** This callable participates in `StructurePrioritySetupRolloutModel`: Expose the deterministic structure rule through the rollout interface. Related public lifecycle methods: {py:obj}`evaluation.rollout.structure_priority_setup.StructurePrioritySetupRolloutModel.policy`, {py:obj}`evaluation.rollout.structure_priority_setup.StructurePrioritySetupRolloutModel.hybrid_action_coordinates`, {py:obj}`evaluation.rollout.structure_priority_setup.StructurePrioritySetupRolloutModel.policy_metadata`, {py:obj}`evaluation.rollout.structure_priority_setup.StructurePrioritySetupRolloutModel.predict`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `StructurePrioritySetupRolloutModel.policy_metadata`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.rollout.structure_priority_setup`

**Purpose:** Return setup-rule identity and permitted-information metadata.

**Exact API:** {py:obj}`evaluation.rollout.structure_priority_setup.StructurePrioritySetupRolloutModel.policy_metadata` · **Source:** [evaluation/rollout/structure_priority_setup.py:191](../../../../evaluation/rollout/structure_priority_setup.py#L191)

**Inputs and outputs:**

- **Returns:**

  ```text
  Provenance metadata emitted by the wrapped policy.
  ```

**Observed usage:**

1. [test fixture: `test_structure_priority_rollout_model_exposes_schema_and_rule_provenance`](../../../../tests/unit/evaluation/test_structure_priority_setup.py#L93)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    policy = _policy()
    model = StructurePrioritySetupRolloutModel(policy)
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)

    action, recurrent_state = model.predict(_observation(candidate_id), deterministic=True)
    metadata = model.policy_metadata

    assert recurrent_state is None
    assert trade_setup_id_from_box(float(action[0])) == candidate_id
    assert model.hybrid_action_coordinates == policy.action_schema.names
    assert metadata["baseline_tier"] == "tier_1_deterministic_structure_rule"
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `StructurePrioritySetupRolloutModel.predict`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.rollout.structure_priority_setup`

**Purpose:** Predict an action while matching the trained-model rollout API.

**Exact API:** {py:obj}`evaluation.rollout.structure_priority_setup.StructurePrioritySetupRolloutModel.predict` · **Source:** [evaluation/rollout/structure_priority_setup.py:199](../../../../evaluation/rollout/structure_priority_setup.py#L199)

**Inputs and outputs:**

- **Args:**

  ```text
  observation: Current environment observation.
  deterministic: Accepted for API compatibility; this policy is deterministic.
  ```

- **Returns:**

  ```text
  Action vector and ``None`` for the unused recurrent state.
  ```

**Observed usage:**

1. [test fixture: `test_structure_priority_rollout_model_exposes_schema_and_rule_provenance`](../../../../tests/unit/evaluation/test_structure_priority_setup.py#L92)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_structure_priority_rollout_model_exposes_schema_and_rule_provenance() -> None:
    policy = _policy()
    model = StructurePrioritySetupRolloutModel(policy)
    candidate_id = trade_setup_candidate_id("fvg_retest", "M5", 1)

    action, recurrent_state = model.predict(_observation(candidate_id), deterministic=True)
    metadata = model.policy_metadata

    assert recurrent_state is None
    assert trade_setup_id_from_box(float(action[0])) == candidate_id
    assert model.hybrid_action_coordinates == policy.action_schema.names
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
