# Learning · `contracts`

This page contains 4 public callable records owned by `learning.contracts`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `FitRequest`

**Kind:** class · **Status:** stable · **Owner:** `learning.contracts`

**Purpose:** Reproducible fitting request without backend-specific model objects.

**Exact API:** {py:obj}`learning.contracts.FitRequest` · **Source:** [learning/contracts.py:14](../../../../learning/contracts.py#L14)

**Observed usage:**

1. [test fixture: `_request`](../../../../tests/unit/learning/test_learning_contracts.py#L27)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _request() -> FitRequest:
    schema = MarketEventSchema("bar", "ohlc-v1", ("time", "close"), "time")
    dataset = DatasetRef(
        "tiny-dataset",
        "US100.cash",
        datetime(2025, 1, 1, tzinfo=UTC),
        datetime(2025, 1, 2, tzinfo=UTC),
        "UTC",
        schema,
        "test-source:sha256:fixture",
    )
    return FitRequest(dataset, "config:sha256:fixture", "input-v1", seed=5, requested_steps=10)
```

2. [test fixture: `test_fit_request_rejects_invalid_seed_and_empty_fit`](../../../../tests/unit/learning/test_learning_contracts.py#L63)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fit_request_rejects_invalid_seed_and_empty_fit() -> None:
    request = _request()
    with pytest.raises(ValueError, match="seed must be nonnegative"):
        FitRequest(
            request.dataset,
            request.config_identity,
            request.input_schema_version,
            seed=-1,
            requested_steps=1,
        )
    with pytest.raises(ValueError, match="requested steps"):
        FitRequest(
            request.dataset,
            request.config_identity,
            request.input_schema_version,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/learning/index`

## `FitResult`

**Kind:** class · **Status:** stable · **Owner:** `learning.contracts`

**Purpose:** Backend-neutral evidence produced by one fitting run.

**Exact API:** {py:obj}`learning.contracts.FitResult` · **Source:** [learning/contracts.py:42](../../../../learning/contracts.py#L42)

**Observed usage:**

1. [test fixture: `fit`](../../../../tests/unit/learning/test_learning_contracts.py#L38)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        artifact = ArtifactRef(
            key="tiny/model",
            media_type="application/octet-stream",
            sha256=hashlib.sha256(payload).hexdigest(),
        )
        return FitResult(
            artifact=artifact,
            dataset=request.dataset,
            config_identity=request.config_identity,
            input_schema_version=request.input_schema_version,
            requested_steps=request.requested_steps,
            training_steps=request.requested_steps,
        )
```

2. [production caller: `fit`](../../../../learning/rl/learner.py#L75)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        digest_builder = hashlib.sha256()
        with saved_path.open("rb") as checkpoint_file:
            for chunk in iter(lambda: checkpoint_file.read(1024 * 1024), b""):
                digest_builder.update(chunk)
        digest = digest_builder.hexdigest()
        return FitResult(
            artifact=ArtifactRef(
                key=f"checkpoint:{saved_path.name}",
                media_type="application/zip",
                sha256=digest,
            ),
            dataset=request.dataset,
            config_identity=request.config_identity,
            input_schema_version=request.input_schema_version,
            requested_steps=request.requested_steps,
            training_steps=int(self.model.num_timesteps),
        )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/learning/index`

## `Learner`

**Kind:** class · **Status:** stable · **Owner:** `learning.contracts`

**Purpose:** Fits model parameters from a stable request and returns artifact identity.

**Exact API:** {py:obj}`learning.contracts.Learner` · **Source:** [learning/contracts.py:65](../../../../learning/contracts.py#L65)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = Learner(...)
```

**Lifecycle context:** Fits model parameters from a stable request and returns artifact identity.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/learning/index`

## `Learner.fit`

**Kind:** method · **Status:** stable · **Owner:** `learning.contracts`

**Purpose:** Fit a learner from the data and parameters in a fit request.

**Exact API:** {py:obj}`learning.contracts.Learner.fit` · **Source:** [learning/contracts.py:68](../../../../learning/contracts.py#L68)

**Inputs and outputs:**

- **Args:**

  ```text
  request: Training data, split boundaries, and learner configuration.
  ```

- **Returns:**

  ```text
  Fitted model or provider together with training metadata.
  ```

**Observed usage:**

1. [test fixture: `test_learner_implementations_share_the_backend_neutral_fit_contract`](../../../../tests/unit/learning/test_learning_contracts.py#L51)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_learner_implementations_share_the_backend_neutral_fit_contract() -> None:
    learner: Learner = _TinyLearner()

    result = learner.fit(_request())

    assert result.config_identity == "config:sha256:fixture"
    assert result.input_schema_version == "input-v1"
    assert result.dataset == _request().dataset
    assert result.training_steps == 10
    assert result.artifact.key == "tiny/model"
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/learning/index`
