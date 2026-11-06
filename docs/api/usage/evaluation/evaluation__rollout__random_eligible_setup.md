# Evaluation · `rollout.random_eligible_setup`

This page contains 14 public callable records owned by `evaluation.rollout.random_eligible_setup`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `AlwaysNoTradePolicy`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Return the versioned NO_TRADE action for every environment decision.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.AlwaysNoTradePolicy` · **Source:** [evaluation/rollout/random_eligible_setup.py:207](../../../../evaluation/rollout/random_eligible_setup.py#L207)

**Observed usage:**

1. [test fixture: `test_existing_policy_rejects_action_schema_mismatch`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L466)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        has_simplex=False,
    ).to_dict()
    incompatible_schema = {**actual_schema, "version": "incompatible-schema"}
    arm = ExistingPolicyArm(
        model=AlwaysNoTradeRolloutModel(
            AlwaysNoTradePolicy(
                build_trade_setup_action_schema(
                    has_sl_mode=False,
                    has_tp_mode=False,
                    has_multi_tp=False,
                    has_simplex=False,
                )
            )
        ),
        metadata={
            "policy_id": "synthetic_policy",
            "checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
            "checkpoint_source_key": "checkpoint",
# … caller assertions omitted …
```

2. [test fixture: `test_tier0_baseline_bundle_has_valid_manifest_and_hashed_artifacts`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L618)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        random_policy_seed=7,
        period_role="synthetic",
        absolute_risk_budget_usd=250.0,
        additional_policies={
            "existing_policy": ExistingPolicyArm(
                model=AlwaysNoTradeRolloutModel(AlwaysNoTradePolicy(action_schema)),
                metadata={
                    "policy_id": "synthetic_existing_policy_seed_12",
                    "checkpoint_sha256": checkpoint_digest,
                    "checkpoint_source_key": "existing_policy_checkpoint",
                    "training_seed": 12,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `AlwaysNoTradeRolloutModel`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Run the always-flat control through the shared policy evaluator.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.AlwaysNoTradeRolloutModel` · **Source:** [evaluation/rollout/random_eligible_setup.py:252](../../../../evaluation/rollout/random_eligible_setup.py#L252)

**Observed usage:**

1. [test fixture: `test_existing_policy_rejects_action_schema_mismatch`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L465)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        has_multi_tp=False,
        has_simplex=False,
    ).to_dict()
    incompatible_schema = {**actual_schema, "version": "incompatible-schema"}
    arm = ExistingPolicyArm(
        model=AlwaysNoTradeRolloutModel(
            AlwaysNoTradePolicy(
                build_trade_setup_action_schema(
                    has_sl_mode=False,
                    has_tp_mode=False,
                    has_multi_tp=False,
                    has_simplex=False,
                )
            )
        ),
        metadata={
            "policy_id": "synthetic_policy",
            "checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
            "checkpoint_source_key": "checkpoint",
            "training_seed": 3,
# … caller assertions omitted …
```

2. [test fixture: `test_tier0_baseline_bundle_has_valid_manifest_and_hashed_artifacts`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L618)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        random_policy_seed=7,
        period_role="synthetic",
        absolute_risk_budget_usd=250.0,
        additional_policies={
            "existing_policy": ExistingPolicyArm(
                model=AlwaysNoTradeRolloutModel(AlwaysNoTradePolicy(action_schema)),
                metadata={
                    "policy_id": "synthetic_existing_policy_seed_12",
                    "checkpoint_sha256": checkpoint_digest,
                    "checkpoint_source_key": "existing_policy_checkpoint",
                    "training_seed": 12,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `RandomEligibleSetupPolicy`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Choose uniformly among eligible setup IDs with an explicit trade rate.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.RandomEligibleSetupPolicy` · **Source:** [evaluation/rollout/random_eligible_setup.py:17](../../../../evaluation/rollout/random_eligible_setup.py#L17)

**Observed usage:**

1. [test fixture: `test_tier0_baselines_record_dollar_band_budget_and_fixed_coordinate`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L420)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        absolute_risk_budget_usd=250.0,
        normalized_risk=1.0,
        additional_policies={
            "existing_policy": ExistingPolicyArm(
                model=RandomEligibleSetupRolloutModel(
                    RandomEligibleSetupPolicy(
                        action_schema,
                        seed=9,
                        normalized_risk=1.0,
                    )
                ),
                metadata={
                    "policy_id": "synthetic_policy",
                    "checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
                    "checkpoint_source_key": "checkpoint",
# … caller assertions omitted …
```

2. [test fixture: `test_random_setup_baseline_uses_shared_rollout_decision_trace`](../../../../tests/integration/evaluation/test_random_eligible_setup_rollout.py#L102)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    assert schema.names[0] == "trade_setup"
    model = RandomEligibleSetupRolloutModel(
        RandomEligibleSetupPolicy(schema, seed=17, trade_probability=1.0)
    )

    result = evaluate_model(
        model,
        bars,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `RandomEligibleSetupRolloutModel`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Adapt the seeded baseline to the shared trained-policy rollout API.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.RandomEligibleSetupRolloutModel` · **Source:** [evaluation/rollout/random_eligible_setup.py:142](../../../../evaluation/rollout/random_eligible_setup.py#L142)

**Observed usage:**

1. [test fixture: `test_tier0_baselines_record_dollar_band_budget_and_fixed_coordinate`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L419)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        period_role="synthetic",
        absolute_risk_budget_usd=250.0,
        normalized_risk=1.0,
        additional_policies={
            "existing_policy": ExistingPolicyArm(
                model=RandomEligibleSetupRolloutModel(
                    RandomEligibleSetupPolicy(
                        action_schema,
                        seed=9,
                        normalized_risk=1.0,
                    )
                ),
                metadata={
                    "policy_id": "synthetic_policy",
                    "checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
                    "checkpoint_source_key": "checkpoint",
                    "training_seed": 3,
# … caller assertions omitted …
```

2. [test fixture: `test_random_setup_baseline_uses_shared_rollout_decision_trace`](../../../../tests/integration/evaluation/test_random_eligible_setup_rollout.py#L101)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        episodic=False,
    )
    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    assert schema.names[0] == "trade_setup"
    model = RandomEligibleSetupRolloutModel(
        RandomEligibleSetupPolicy(schema, seed=17, trade_probability=1.0)
    )

    result = evaluate_model(
        model,
        bars,
        features,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `AlwaysNoTradePolicy`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Return the versioned NO_TRADE action for every environment decision.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.AlwaysNoTradePolicy` · **Source:** [evaluation/rollout/random_eligible_setup.py:207](../../../../evaluation/rollout/random_eligible_setup.py#L207)

**Observed usage:**

1. [test fixture: `test_existing_policy_rejects_action_schema_mismatch`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L466)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        has_simplex=False,
    ).to_dict()
    incompatible_schema = {**actual_schema, "version": "incompatible-schema"}
    arm = ExistingPolicyArm(
        model=AlwaysNoTradeRolloutModel(
            AlwaysNoTradePolicy(
                build_trade_setup_action_schema(
                    has_sl_mode=False,
                    has_tp_mode=False,
                    has_multi_tp=False,
                    has_simplex=False,
                )
            )
        ),
        metadata={
            "policy_id": "synthetic_policy",
            "checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
            "checkpoint_source_key": "checkpoint",
# … caller assertions omitted …
```

2. [test fixture: `test_tier0_baseline_bundle_has_valid_manifest_and_hashed_artifacts`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L618)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        random_policy_seed=7,
        period_role="synthetic",
        absolute_risk_budget_usd=250.0,
        additional_policies={
            "existing_policy": ExistingPolicyArm(
                model=AlwaysNoTradeRolloutModel(AlwaysNoTradePolicy(action_schema)),
                metadata={
                    "policy_id": "synthetic_existing_policy_seed_12",
                    "checkpoint_sha256": checkpoint_digest,
                    "checkpoint_source_key": "existing_policy_checkpoint",
                    "training_seed": 12,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `AlwaysNoTradeRolloutModel`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Run the always-flat control through the shared policy evaluator.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.AlwaysNoTradeRolloutModel` · **Source:** [evaluation/rollout/random_eligible_setup.py:252](../../../../evaluation/rollout/random_eligible_setup.py#L252)

**Observed usage:**

1. [test fixture: `test_existing_policy_rejects_action_schema_mismatch`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L465)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        has_multi_tp=False,
        has_simplex=False,
    ).to_dict()
    incompatible_schema = {**actual_schema, "version": "incompatible-schema"}
    arm = ExistingPolicyArm(
        model=AlwaysNoTradeRolloutModel(
            AlwaysNoTradePolicy(
                build_trade_setup_action_schema(
                    has_sl_mode=False,
                    has_tp_mode=False,
                    has_multi_tp=False,
                    has_simplex=False,
                )
            )
        ),
        metadata={
            "policy_id": "synthetic_policy",
            "checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
            "checkpoint_source_key": "checkpoint",
            "training_seed": 3,
# … caller assertions omitted …
```

2. [test fixture: `test_tier0_baseline_bundle_has_valid_manifest_and_hashed_artifacts`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L618)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        random_policy_seed=7,
        period_role="synthetic",
        absolute_risk_budget_usd=250.0,
        additional_policies={
            "existing_policy": ExistingPolicyArm(
                model=AlwaysNoTradeRolloutModel(AlwaysNoTradePolicy(action_schema)),
                metadata={
                    "policy_id": "synthetic_existing_policy_seed_12",
                    "checkpoint_sha256": checkpoint_digest,
                    "checkpoint_source_key": "existing_policy_checkpoint",
                    "training_seed": 12,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `RandomEligibleSetupPolicy`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Choose uniformly among eligible setup IDs with an explicit trade rate.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.RandomEligibleSetupPolicy` · **Source:** [evaluation/rollout/random_eligible_setup.py:17](../../../../evaluation/rollout/random_eligible_setup.py#L17)

**Observed usage:**

1. [test fixture: `test_tier0_baselines_record_dollar_band_budget_and_fixed_coordinate`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L420)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        absolute_risk_budget_usd=250.0,
        normalized_risk=1.0,
        additional_policies={
            "existing_policy": ExistingPolicyArm(
                model=RandomEligibleSetupRolloutModel(
                    RandomEligibleSetupPolicy(
                        action_schema,
                        seed=9,
                        normalized_risk=1.0,
                    )
                ),
                metadata={
                    "policy_id": "synthetic_policy",
                    "checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
                    "checkpoint_source_key": "checkpoint",
# … caller assertions omitted …
```

2. [test fixture: `test_random_setup_baseline_uses_shared_rollout_decision_trace`](../../../../tests/integration/evaluation/test_random_eligible_setup_rollout.py#L102)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    assert schema.names[0] == "trade_setup"
    model = RandomEligibleSetupRolloutModel(
        RandomEligibleSetupPolicy(schema, seed=17, trade_probability=1.0)
    )

    result = evaluate_model(
        model,
        bars,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `RandomEligibleSetupRolloutModel`

**Kind:** class · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Adapt the seeded baseline to the shared trained-policy rollout API.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.RandomEligibleSetupRolloutModel` · **Source:** [evaluation/rollout/random_eligible_setup.py:142](../../../../evaluation/rollout/random_eligible_setup.py#L142)

**Observed usage:**

1. [test fixture: `test_tier0_baselines_record_dollar_band_budget_and_fixed_coordinate`](../../../../tests/integration/evaluation/test_matched_setup_baselines.py#L419)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        period_role="synthetic",
        absolute_risk_budget_usd=250.0,
        normalized_risk=1.0,
        additional_policies={
            "existing_policy": ExistingPolicyArm(
                model=RandomEligibleSetupRolloutModel(
                    RandomEligibleSetupPolicy(
                        action_schema,
                        seed=9,
                        normalized_risk=1.0,
                    )
                ),
                metadata={
                    "policy_id": "synthetic_policy",
                    "checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
                    "checkpoint_source_key": "checkpoint",
                    "training_seed": 3,
# … caller assertions omitted …
```

2. [test fixture: `test_random_setup_baseline_uses_shared_rollout_decision_trace`](../../../../tests/integration/evaluation/test_random_eligible_setup_rollout.py#L101)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        episodic=False,
    )
    schema = env.action_schema
    assert isinstance(schema, TradeSetupActionSchema)
    assert schema.names[0] == "trade_setup"
    model = RandomEligibleSetupRolloutModel(
        RandomEligibleSetupPolicy(schema, seed=17, trade_probability=1.0)
    )

    result = evaluate_model(
        model,
        bars,
        features,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `AlwaysNoTradePolicy.metadata`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Identify this policy as the always-flat accounting control.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.AlwaysNoTradePolicy.metadata` · **Source:** [evaluation/rollout/random_eligible_setup.py:232](../../../../evaluation/rollout/random_eligible_setup.py#L232)

**Inputs and outputs:**

- **Returns:**

  ```text
  Provenance metadata identifying the no-trade baseline.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = AlwaysNoTradePolicy(...)
result = instance.metadata()
```

**Lifecycle context:** This callable participates in `AlwaysNoTradePolicy`: Return the versioned NO_TRADE action for every environment decision. Related public lifecycle methods: {py:obj}`evaluation.rollout.random_eligible_setup.AlwaysNoTradePolicy.metadata`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `RandomEligibleSetupPolicy.metadata`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Return settings that identify and reproduce this policy instance.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.RandomEligibleSetupPolicy.metadata` · **Source:** [evaluation/rollout/random_eligible_setup.py:109](../../../../evaluation/rollout/random_eligible_setup.py#L109)

**Inputs and outputs:**

- **Returns:**

  ```text
  Tier, rationale, permitted information, fit/selection status,
  action schema, seed, trade probability, risk, and action conventions.
  ```

**Observed usage:**

1. [test fixture: `test_random_eligible_policy_supports_abstention_and_fixed_risk`](../../../../tests/unit/evaluation/test_random_eligible_setup.py#L54)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    action = policy(observation)

    assert trade_setup_id_from_box(float(action[0])) == NO_TRADE_ID
    assert action[schema.names.index("risk")] == pytest.approx(-0.5)
    metadata = policy.metadata()
    assert metadata["policy_id"] == "random_eligible_trade_setup_v1"
    assert metadata["baseline_tier"] == "tier_0_accounting_and_decision_sanity"
    assert metadata["permitted_information"] == ["current_observation.trade_setup_mask"]
    assert metadata["training_performed"] is False
    assert metadata["selection_or_tuning_performed"] is False
```

2. [test fixture: `test_random_setup_baseline_keeps_market_execution_when_schema_offers_limits`](../../../../tests/unit/evaluation/test_random_eligible_setup.py#L77)

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

## `RandomEligibleSetupRolloutModel.hybrid_action_coordinates`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Return the exact action-coordinate names used by the baseline.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.RandomEligibleSetupRolloutModel.hybrid_action_coordinates` · **Source:** [evaluation/rollout/random_eligible_setup.py:168](../../../../evaluation/rollout/random_eligible_setup.py#L168)

**Inputs and outputs:**

- **Returns:**

  ```text
  Ordered coordinate names from the policy action schema.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = RandomEligibleSetupRolloutModel(...)
value = instance.hybrid_action_coordinates
```

**Lifecycle context:** This callable participates in `RandomEligibleSetupRolloutModel`: Adapt the seeded baseline to the shared trained-policy rollout API. Related public lifecycle methods: {py:obj}`evaluation.rollout.random_eligible_setup.RandomEligibleSetupRolloutModel.policy`, {py:obj}`evaluation.rollout.random_eligible_setup.RandomEligibleSetupRolloutModel.hybrid_action_coordinates`, {py:obj}`evaluation.rollout.random_eligible_setup.RandomEligibleSetupRolloutModel.policy_metadata`, {py:obj}`evaluation.rollout.random_eligible_setup.RandomEligibleSetupRolloutModel.predict`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `RandomEligibleSetupRolloutModel.policy`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Expose the semantic action coordinates used by rollout diagnostics.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.RandomEligibleSetupRolloutModel.policy` · **Source:** [evaluation/rollout/random_eligible_setup.py:159](../../../../evaluation/rollout/random_eligible_setup.py#L159)

**Inputs and outputs:**

- **Returns:**

  ```text
  This rollout-compatible model wrapper.
  ```

**Observed usage:**

1. [test fixture: `test_random_eligible_rollout_model_uses_shared_action_adapter`](../../../../tests/unit/evaluation/test_random_eligible_setup.py#L110)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    rollout_action = make_action_fn(model, strategy_actions=True)(observation)

    np.testing.assert_array_equal(direct_action, expected(observation))
    np.testing.assert_array_equal(rollout_action, expected(observation))
    assert recurrent_state is None
    assert model.policy.hybrid_action_coordinates == schema.names
    assert model.policy_metadata["seed"] == 31
    assert model.policy_metadata["execution_and_risk_controls"] == (
        "delegated to shared evaluation environment"
    )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `RandomEligibleSetupRolloutModel.policy_metadata`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Return seed and action semantics for a future result manifest.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.RandomEligibleSetupRolloutModel.policy_metadata` · **Source:** [evaluation/rollout/random_eligible_setup.py:177](../../../../evaluation/rollout/random_eligible_setup.py#L177)

**Inputs and outputs:**

- **Returns:**

  ```text
  Baseline identity, seed, action schema, and policy semantics.
  ```

**Observed usage:**

1. [test fixture: `test_random_eligible_rollout_model_uses_shared_action_adapter`](../../../../tests/unit/evaluation/test_random_eligible_setup.py#L111)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    np.testing.assert_array_equal(direct_action, expected(observation))
    np.testing.assert_array_equal(rollout_action, expected(observation))
    assert recurrent_state is None
    assert model.policy.hybrid_action_coordinates == schema.names
    assert model.policy_metadata["seed"] == 31
    assert model.policy_metadata["execution_and_risk_controls"] == (
        "delegated to shared evaluation environment"
    )
```

2. [production caller: `evaluate_tier0_setup_baselines`](../../../../evaluation/rollout/matched_setup_baselines.py#L449)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        if "trade_setup" not in schema.names or "risk" not in schema.names:
            raise ValueError("configured environment action schema lacks setup or risk coordinates")

        if baseline_name == "always_no_trade":
            model: Any = AlwaysNoTradeRolloutModel(AlwaysNoTradePolicy(schema))
            metadata = dict(model.policy_metadata)
            deterministic = True
        elif baseline_name == "random_eligible_setup":
            model = RandomEligibleSetupRolloutModel(
                RandomEligibleSetupPolicy(
                    schema,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `RandomEligibleSetupRolloutModel.predict`

**Kind:** method · **Status:** stable · **Owner:** `evaluation.rollout.random_eligible_setup`

**Purpose:** Return a schema-compatible random action and empty recurrent state.

**Exact API:** {py:obj}`evaluation.rollout.random_eligible_setup.RandomEligibleSetupRolloutModel.predict` · **Source:** [evaluation/rollout/random_eligible_setup.py:185](../../../../evaluation/rollout/random_eligible_setup.py#L185)

**Inputs and outputs:**

- **Args:**

  ```text
  observation: Environment observation containing the eligible setup mask.
  deterministic: Accepted for rollout compatibility and otherwise ignored.
  ```

- **Returns:**

  ```text
  Action vector and ``None`` recurrent state.
  ```

**Observed usage:**

1. [test fixture: `test_random_eligible_rollout_model_uses_shared_action_adapter`](../../../../tests/unit/evaluation/test_random_eligible_setup.py#L104)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    policy = RandomEligibleSetupPolicy(schema, seed=31, normalized_risk=0.4)
    model = RandomEligibleSetupRolloutModel(policy)
    observation = _observation(2, 7, 31)
    expected = RandomEligibleSetupPolicy(schema, seed=31, normalized_risk=0.4)

    direct_action, recurrent_state = model.predict(observation, deterministic=True)
    rollout_action = make_action_fn(model, strategy_actions=True)(observation)

    np.testing.assert_array_equal(direct_action, expected(observation))
    np.testing.assert_array_equal(rollout_action, expected(observation))
    assert recurrent_state is None
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
