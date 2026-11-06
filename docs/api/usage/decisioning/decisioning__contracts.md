# Decisioning · `contracts`

This page contains 12 public callable records owned by `decisioning.contracts`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ActionSchemaRef`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.contracts`

**Purpose:** Names and version of the action layout used by a decision.

**Exact API:** {py:obj}`decisioning.contracts.ActionSchemaRef` · **Source:** [decisioning/contracts.py:15](../../../../decisioning/contracts.py#L15)

**Observed usage:**

1. [test fixture: `test_structured_conversion_requires_exact_coordinate_set`](../../../../tests/integration/test_sb3_adapter.py#L163)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    decision = SB3DecisionProvider(model, input_schema_version="observation-v1").predict(_input())
    assert isinstance(decision.action, StructuredAction)

    inconsistent = Decision(
        action=StructuredAction({"risk": 0.1}),
        action_schema=ActionSchemaRef(
            version="overlay-v2", key="2", coordinates=("risk", "target"), kind="continuous"
        ),
    )
    with pytest.raises(ValueError, match="coordinates disagree"):
        to_policy_action(inconsistent)
```

2. [test fixture: `test_policy_action_conversion_rejects_actions_that_disagree_with_schema`](../../../../tests/integration/test_sb3_adapter.py#L176)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_policy_action_conversion_rejects_actions_that_disagree_with_schema(
    decision: Decision,
) -> None:
    with pytest.raises(ValueError):
        to_policy_action(decision)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `ContinuousAction`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.contracts`

**Purpose:** A scalar continuous action in the provider's declared action schema.

**Exact API:** {py:obj}`decisioning.contracts.ContinuousAction` · **Source:** [decisioning/contracts.py:41](../../../../decisioning/contracts.py#L41)

**Observed usage:**

1. [test fixture: `test_policy_action_conversion_rejects_actions_that_disagree_with_schema`](../../../../tests/integration/test_sb3_adapter.py#L181)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_policy_action_conversion_rejects_actions_that_disagree_with_schema(
    decision: Decision,
) -> None:
    with pytest.raises(ValueError):
        to_policy_action(decision)
```

2. [test fixture: `test_provider_rollout_adapter_returns_environment_action`](../../../../tests/unit/evaluation/test_decision_provider_rollout.py#L57)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `Decision`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.contracts`

**Purpose:** A semantic action and the schema that defines its meaning.

**Exact API:** {py:obj}`decisioning.contracts.Decision` · **Source:** [decisioning/contracts.py:58](../../../../decisioning/contracts.py#L58)

**Observed usage:**

1. [test fixture: `test_structured_conversion_requires_exact_coordinate_set`](../../../../tests/integration/test_sb3_adapter.py#L161)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        np.asarray([0.1, 0.2], dtype=np.float32),
    )
    decision = SB3DecisionProvider(model, input_schema_version="observation-v1").predict(_input())
    assert isinstance(decision.action, StructuredAction)

    inconsistent = Decision(
        action=StructuredAction({"risk": 0.1}),
        action_schema=ActionSchemaRef(
            version="overlay-v2", key="2", coordinates=("risk", "target"), kind="continuous"
        ),
    )
    with pytest.raises(ValueError, match="coordinates disagree"):
        to_policy_action(inconsistent)
```

2. [test fixture: `test_policy_action_conversion_rejects_actions_that_disagree_with_schema`](../../../../tests/integration/test_sb3_adapter.py#L174)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_policy_action_conversion_rejects_actions_that_disagree_with_schema(
    decision: Decision,
) -> None:
    with pytest.raises(ValueError):
        to_policy_action(decision)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `DecisionArtifactRef`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.contracts`

**Purpose:** Stable identifier for a persisted provider or model bundle.

**Exact API:** {py:obj}`decisioning.contracts.DecisionArtifactRef` · **Source:** [decisioning/contracts.py:77](../../../../decisioning/contracts.py#L77)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = DecisionArtifactRef(...)
```

**Lifecycle context:** Stable identifier for a persisted provider or model bundle.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `DecisionInput`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.contracts`

**Purpose:** An observation plus its versioned semantic schema.

**Exact API:** {py:obj}`decisioning.contracts.DecisionInput` · **Source:** [decisioning/contracts.py:25](../../../../decisioning/contracts.py#L25)

**Observed usage:**

1. [test fixture: `_input`](../../../../tests/integration/test_sb3_adapter.py#L38)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _input(schema_version: str = "observation-v1") -> DecisionInput:
    return DecisionInput({"seq": np.zeros((2, 3), dtype=np.float32)}, schema_version)
```

2. [test fixture: `test_supervised_learner_fits_self_describing_artifact_and_provider`](../../../../tests/unit/learning/test_learning_supervised_reference.py#L67)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert result.training_steps == 8
    provider = load_reference_torch_provider(checkpoint)
    assert provider.metadata.training_paradigm == "supervised"
    assert provider.metadata.model_family == "torch_mlp_classifier"
    decision = provider.predict(
        DecisionInput(
            observation={
                "seq": np.zeros((10, 2), dtype=np.float32),
                "account": np.zeros(6, dtype=np.float32),
            },
            schema_version="account-state-v1",
        ),
    )
    assert isinstance(decision.action, DiscreteAction)
    assert (
        decision.action.name == provider.metadata.action_schema.coordinates[decision.action.index]
    )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `DecisionProvider`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.contracts`

**Purpose:** Produces one schema-validated decision for each observation.

**Exact API:** {py:obj}`decisioning.contracts.DecisionProvider` · **Source:** [decisioning/contracts.py:85](../../../../decisioning/contracts.py#L85)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = DecisionProvider(...)
```

**Lifecycle context:** Produces one schema-validated decision for each observation.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `DiscreteAction`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.contracts`

**Purpose:** A categorical choice with its stable category name.

**Exact API:** {py:obj}`decisioning.contracts.DiscreteAction` · **Source:** [decisioning/contracts.py:33](../../../../decisioning/contracts.py#L33)

**Observed usage:**

1. [test fixture: `test_discrete_provider_names_action_and_preserves_determinism`](../../../../tests/integration/test_sb3_adapter.py#L52)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    provider = SB3DecisionProvider(model, input_schema_version="observation-v1")

    decision = provider.predict(_input(), deterministic=False)

    assert decision.action == DiscreteAction(index=1, name="enter_long")
    assert to_policy_action(decision) == 1
    assert model.calls[0][1] is False
    assert provider.metadata.action_schema.coordinates == names
```

2. [test fixture: `test_policy_action_conversion_rejects_actions_that_disagree_with_schema`](../../../../tests/integration/test_sb3_adapter.py#L175)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_policy_action_conversion_rejects_actions_that_disagree_with_schema(
    decision: Decision,
) -> None:
    with pytest.raises(ValueError):
        to_policy_action(decision)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `PredictorMetadata`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.contracts`

**Purpose:** Backend-neutral description of a provider's input and output.

**Exact API:** {py:obj}`decisioning.contracts.PredictorMetadata` · **Source:** [decisioning/contracts.py:66](../../../../decisioning/contracts.py#L66)

**Observed usage:**

1. [test fixture: `__init__`](../../../../tests/unit/evaluation/test_decision_provider_rollout.py#L28)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def __init__(self, action: Decision) -> None:
    self.action = action
    self.inputs: list[tuple[DecisionInput, bool]] = []
    self.metadata = PredictorMetadata(
        provider_id="test",
        model_family="test-provider",
        training_paradigm="test",
        input_schema_version="obs-v1",
        action_schema=ActionSchemaRef(
            version="test-v1", key="test", coordinates=("action",), kind="test"
        ),
    )
```

2. [test fixture: `test_rule_and_sb3_providers_share_the_same_rollout_boundary`](../../../../tests/unit/evaluation/test_decision_provider_rollout.py#L109)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_rule_and_sb3_providers_share_the_same_rollout_boundary() -> None:
    action_schema = ActionSchemaRef(
        version="discrete-v1", key="hold-enter", coordinates=("hold", "enter"), kind="discrete"
    )
    metadata = PredictorMetadata(
        provider_id="rule",
        model_family="rule",
        training_paradigm="rule_based",
        input_schema_version="obs-v1",
        action_schema=action_schema,
    )
    rule_provider = RuleBasedDecisionProvider(
        lambda _: Decision(DiscreteAction(1, "enter"), action_schema), metadata
    )

    class _SB3Policy:
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `StructuredAction`

**Kind:** class · **Status:** stable · **Owner:** `decisioning.contracts`

**Purpose:** Named continuous coordinates from a versioned action schema.

**Exact API:** {py:obj}`decisioning.contracts.StructuredAction` · **Source:** [decisioning/contracts.py:48](../../../../decisioning/contracts.py#L48)

**Observed usage:**

1. [test fixture: `test_box_provider_returns_named_structured_coordinates_in_schema_order`](../../../../tests/integration/test_sb3_adapter.py#L87)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_box_provider_returns_named_structured_coordinates_in_schema_order() -> None:
    coordinates = ("direction", "risk", "target")
    model = _Policy(
        spaces.Box(-1.0, 1.0, shape=(3,), dtype=np.float32),
        {"version": "overlay-v2", "key": "3", "coordinates": coordinates},
        np.asarray([0.25, -0.5, 1.0], dtype=np.float32),
    )
    provider = SB3DecisionProvider(model, input_schema_version="observation-v1")

    decision = provider.predict(_input())

    assert decision.action == StructuredAction({"direction": 0.25, "risk": -0.5, "target": 1.0})
    np.testing.assert_array_equal(to_policy_action(decision), [0.25, -0.5, 1.0])
```

2. [test fixture: `test_structured_conversion_requires_exact_coordinate_set`](../../../../tests/integration/test_sb3_adapter.py#L162)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )
    decision = SB3DecisionProvider(model, input_schema_version="observation-v1").predict(_input())
    assert isinstance(decision.action, StructuredAction)

    inconsistent = Decision(
        action=StructuredAction({"risk": 0.1}),
        action_schema=ActionSchemaRef(
            version="overlay-v2", key="2", coordinates=("risk", "target"), kind="continuous"
        ),
    )
    with pytest.raises(ValueError, match="coordinates disagree"):
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `to_policy_action`

**Kind:** function · **Status:** stable · **Owner:** `decisioning.contracts`

**Purpose:** Convert a decision back to the action representation expected by Gym.

**Exact API:** {py:obj}`decisioning.contracts.to_policy_action` · **Source:** [decisioning/contracts.py:110](../../../../decisioning/contracts.py#L110)

**Inputs and outputs:**

- **Args:**

  ```text
  decision: Decision used by the operation described above.
  ```

- **Returns:**

  ```text
  Array returned by ``to_policy_action``.
  ```

**Observed usage:**

1. [test fixture: `test_discrete_provider_names_action_and_preserves_determinism`](../../../../tests/integration/test_sb3_adapter.py#L53)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    provider = SB3DecisionProvider(model, input_schema_version="observation-v1")

    decision = provider.predict(_input(), deterministic=False)

    assert decision.action == DiscreteAction(index=1, name="enter_long")
    assert to_policy_action(decision) == 1
    assert model.calls[0][1] is False
    assert provider.metadata.action_schema.coordinates == names
```

2. [test fixture: `test_box_provider_returns_named_structured_coordinates_in_schema_order`](../../../../tests/integration/test_sb3_adapter.py#L88)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_box_provider_returns_named_structured_coordinates_in_schema_order() -> None:
    coordinates = ("direction", "risk", "target")
    model = _Policy(
        spaces.Box(-1.0, 1.0, shape=(3,), dtype=np.float32),
        {"version": "overlay-v2", "key": "3", "coordinates": coordinates},
        np.asarray([0.25, -0.5, 1.0], dtype=np.float32),
    )
    provider = SB3DecisionProvider(model, input_schema_version="observation-v1")

    decision = provider.predict(_input())

    assert decision.action == StructuredAction({"direction": 0.25, "risk": -0.5, "target": 1.0})
    np.testing.assert_array_equal(to_policy_action(decision), [0.25, -0.5, 1.0])
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `DecisionProvider.metadata`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.contracts`

**Purpose:** Describe the input and output contract implemented by this provider.

**Exact API:** {py:obj}`decisioning.contracts.DecisionProvider.metadata` · **Source:** [decisioning/contracts.py:89](../../../../decisioning/contracts.py#L89)

**Inputs and outputs:**

- **Returns:**

  ```text
  Result of describe the input and output contract implemented by this provider.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = DecisionProvider(...)
value = instance.metadata
```

**Lifecycle context:** This callable participates in `DecisionProvider`: Produces one schema-validated decision for each observation. Related public lifecycle methods: {py:obj}`decisioning.contracts.DecisionProvider.metadata`, {py:obj}`decisioning.contracts.DecisionProvider.predict`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`

## `DecisionProvider.predict`

**Kind:** method · **Status:** stable · **Owner:** `decisioning.contracts`

**Purpose:** Produce an action for one versioned decision input.

**Exact API:** {py:obj}`decisioning.contracts.DecisionProvider.predict` · **Source:** [decisioning/contracts.py:97](../../../../decisioning/contracts.py#L97)

**Inputs and outputs:**

- **Args:**

  ```text
  input: Observation and schema identity to evaluate.
  deterministic: Select the deterministic policy action when supported.
  ```

- **Returns:**

  ```text
  Versioned decision output compatible with the input contract.
  ```

**Observed usage:**

1. [production caller: `action_fn`](../../../../evaluation/rollout/provider.py#L46)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def action_fn(observation: dict[str, Any]) -> int | float | np.ndarray[Any, Any]:
    decision = provider.predict(
        DecisionInput(observation=observation, schema_version=input_schema_version),
        deterministic=deterministic,
    )
    action = to_policy_action(decision)
    if strategy_actions:
        return np.asarray(action, dtype=np.float32).reshape(-1)
    values = np.asarray(action, dtype=np.float32).reshape(-1)
    if continuous_actions:
        return float(values[0])
    return int(values[0])
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/decisioning/index`
