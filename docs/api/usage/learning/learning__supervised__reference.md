# Learning · `supervised.reference`

This page contains 7 public callable records owned by `learning.supervised.reference`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ReferenceTorchLearner`

**Kind:** class · **Status:** stable · **Owner:** `learning.supervised.reference`

**Purpose:** Fit a small categorical classifier and persist a self-describing artifact.

**Exact API:** {py:obj}`learning.supervised.reference.ReferenceTorchLearner` · **Source:** [learning/supervised/reference.py:145](../../../../learning/supervised/reference.py#L145)

**Observed usage:**

1. [production caller: `build_reference_torch_learner`](../../../../learning/supervised/reference.py#L323)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def build_reference_torch_learner(
    observations: Mapping[str, np.ndarray[Any, Any]],
    labels: np.ndarray[Any, Any],
    *,
    checkpoint_path: str | Path,
    learning_rate: float = 1e-2,
) -> Learner:
    return ReferenceTorchLearner(
        observations,
        labels,
        checkpoint_path=checkpoint_path,
        learning_rate=learning_rate,
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/learning/index`

## `ReferenceTorchProvider`

**Kind:** class · **Status:** stable · **Owner:** `learning.supervised.reference`

**Purpose:** Wrap a fitted Torch classifier as a backend-neutral decision provider.

**Exact API:** {py:obj}`learning.supervised.reference.ReferenceTorchProvider` · **Source:** [learning/supervised/reference.py:78](../../../../learning/supervised/reference.py#L78)

**Observed usage:**

1. [production caller: `fit`](../../../../learning/supervised/reference.py#L230)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                "state_dict": model.state_dict(),
            },
            self.checkpoint_path,
        )
        digest = hashlib.sha256(self.checkpoint_path.read_bytes()).hexdigest()
        self.provider = ReferenceTorchProvider(
            model,
            input_schema_version=request.input_schema_version,
            action_schema=action_schema,
        )
        return FitResult(
            artifact=ArtifactRef(
                key=f"model:{self.checkpoint_path.name}",
                media_type="application/x-pytorch-state-dict",
                sha256=digest,
# … caller assertions omitted …
```

2. [production caller: `load_reference_torch_provider`](../../../../learning/supervised/reference.py#L298)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        raise ValueError("reference classifier action schema is invalid")
    model = _ReferenceClassifier(
        (int(sequence_shape[0]), int(sequence_shape[1])), account_width, len(coordinates)
    )
    model.load_state_dict(state_dict)
    return ReferenceTorchProvider(
        model,
        input_schema_version=input_schema_version,
        action_schema=action_schema,
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/learning/index`

## `build_reference_torch_learner`

**Kind:** function · **Status:** stable · **Owner:** `learning.supervised.reference`

**Purpose:** Construct the optional supervised reference backend.

**Exact API:** {py:obj}`learning.supervised.reference.build_reference_torch_learner` · **Source:** [learning/supervised/reference.py:305](../../../../learning/supervised/reference.py#L305)

**Inputs and outputs:**

- **Args:**

  ```text
  observations: Observations to evaluate, in input order.
  labels: Labels used by the operation described above.
  checkpoint_path: Path or filename identifying the checkpoint.
  learning_rate: Numeric value used for the learning rate.
  ```

- **Returns:**

  ```text
  Result of construct the optional supervised reference backend.
  ```

**Observed usage:**

1. [production caller: `build_learner`](../../../../learning/learner_factory.py#L27)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def build_learner(backend: str, **options: Any) -> Learner:
    if backend == "stable_baselines3":
        from learning.rl.learner import build_sb3_learner

        return build_sb3_learner(**options)
    if backend == "supervised_torch_reference":
        from learning.supervised.reference import build_reference_torch_learner

        return build_reference_torch_learner(**options)
    raise ValueError(f"unsupported learning backend: {backend!r}")
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/learning/index`

## `load_reference_torch_provider`

**Kind:** function · **Status:** stable · **Owner:** `learning.supervised.reference`

**Purpose:** Load a reference artifact and validate its declared schemas before use.

**Exact API:** {py:obj}`learning.supervised.reference.load_reference_torch_provider` · **Source:** [learning/supervised/reference.py:249](../../../../learning/supervised/reference.py#L249)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input file or directory.
  ```

- **Returns:**

  ```text
  Result of load a reference artifact and validate its declared schemas before use.
  ```

**Observed usage:**

1. [test fixture: `test_supervised_learner_fits_self_describing_artifact_and_provider`](../../../../tests/unit/learning/test_learning_supervised_reference.py#L63)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    result = learner.fit(_request())

    assert checkpoint.is_file()
    assert result.artifact.sha256
    assert result.training_steps == 8
    provider = load_reference_torch_provider(checkpoint)
    assert provider.metadata.training_paradigm == "supervised"
    assert provider.metadata.model_family == "torch_mlp_classifier"
    decision = provider.predict(
        DecisionInput(
            observation={
# … caller assertions omitted …
```

2. [test fixture: `test_supervised_provider_runs_through_shared_evaluation_path`](../../../../tests/unit/learning/test_learning_supervised_reference.py#L84)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_supervised_provider_runs_through_shared_evaluation_path(tmp_path: Path) -> None:
    learner = _learner(tmp_path / "classifier.pt")
    learner.fit(_request())
    provider = load_reference_torch_provider(tmp_path / "classifier.pt")

    index = pd.date_range("2025-01-06 16:30", periods=32, freq="1min", tz="Etc/GMT-3")
    close = 20_000.0 + np.arange(len(index), dtype=np.float64) * 0.1
    bars = pd.DataFrame(
        {
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/learning/index`

## `ReferenceTorchLearner.fit`

**Kind:** method · **Status:** stable · **Owner:** `learning.supervised.reference`

**Purpose:** Fit the reference PyTorch policy on the supplied supervised examples.

**Exact API:** {py:obj}`learning.supervised.reference.ReferenceTorchLearner.fit` · **Source:** [learning/supervised/reference.py:170](../../../../learning/supervised/reference.py#L170)

**Inputs and outputs:**

- **Args:**

  ```text
  request: Arrays, split information, and learner configuration.
  ```

- **Returns:**

  ```text
  Fitted provider and training metadata.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = ReferenceTorchLearner(...)
result = instance.fit(request=...)
```

**Lifecycle context:** This callable participates in `ReferenceTorchLearner`: Fit a small categorical classifier and persist a self-describing artifact. Related public lifecycle methods: {py:obj}`learning.supervised.reference.ReferenceTorchLearner.fit`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/learning/index`

## `ReferenceTorchProvider.metadata`

**Kind:** method · **Status:** stable · **Owner:** `learning.supervised.reference`

**Purpose:** Return schema and provenance metadata for the fitted model.

**Exact API:** {py:obj}`learning.supervised.reference.ReferenceTorchProvider.metadata` · **Source:** [learning/supervised/reference.py:105](../../../../learning/supervised/reference.py#L105)

**Inputs and outputs:**

- **Returns:**

  ```text
  Result of return schema and provenance metadata for the fitted model.
  ```

**Observed usage:**

1. [test fixture: `test_supervised_learner_fits_self_describing_artifact_and_provider`](../../../../tests/unit/learning/test_learning_supervised_reference.py#L64)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    assert checkpoint.is_file()
    assert result.artifact.sha256
    assert result.training_steps == 8
    provider = load_reference_torch_provider(checkpoint)
    assert provider.metadata.training_paradigm == "supervised"
    assert provider.metadata.model_family == "torch_mlp_classifier"
    decision = provider.predict(
        DecisionInput(
            observation={
                "seq": np.zeros((10, 2), dtype=np.float32),
# … caller assertions omitted …
```

2. [production caller: `predict`](../../../../learning/supervised/reference.py#L124)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
        del deterministic  # Classification uses deterministic argmax inference.
        if input.schema_version != self.metadata.input_schema_version:
            raise ValueError("decision input schema does not match the fitted predictor")
        sequence = np.asarray(input.observation["seq"], dtype=np.float32)
        account = np.asarray(input.observation["account"], dtype=np.float32)
        if sequence.ndim != 2 or account.ndim != 1:
            raise ValueError("reference classifier expects one sequence and one account vector")
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/learning/index`

## `ReferenceTorchProvider.predict`

**Kind:** method · **Status:** stable · **Owner:** `learning.supervised.reference`

**Purpose:** Predict one action from a versioned observation.

**Exact API:** {py:obj}`learning.supervised.reference.ReferenceTorchProvider.predict` · **Source:** [learning/supervised/reference.py:113](../../../../learning/supervised/reference.py#L113)

**Inputs and outputs:**

- **Args:**

  ```text
  input: Versioned observation and schema identity.
  deterministic: Use the deterministic action when supported.
  ```

- **Returns:**

  ```text
  Action output with matching schema metadata.
  ```

**Observed usage:**

1. [test fixture: `test_supervised_learner_fits_self_describing_artifact_and_provider`](../../../../tests/unit/learning/test_learning_supervised_reference.py#L66)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert result.artifact.sha256
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

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/learning/index`
