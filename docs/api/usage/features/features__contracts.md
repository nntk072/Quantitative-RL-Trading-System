# Features · `contracts`

This page contains 2 public callable records owned by `features.contracts`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `InputSchema`

**Kind:** class · **Status:** stable · **Owner:** `features.contracts`

**Purpose:** Versioned schema describing a model input tensor or array.

**Exact API:** {py:obj}`features.contracts.InputSchema` · **Source:** [features/contracts.py:13](../../../../features/contracts.py#L13)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `test_distinct_input_representations_share_one_schema_contract`](../../../../tests/unit/market_data/test_input_view_contract.py#L13)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_distinct_input_representations_share_one_schema_contract(kind: InputKind) -> None:
    schema = InputSchema("market-input", "v1", kind, ("x0", "x1"))

    view = InputView(schema, "dataset-1", ((0.1, 0.2), (0.3, 0.4)))

    assert view.schema.kind == kind
    assert len(view.values) == 2
```

2. [test fixture: `test_input_view_rejects_width_schema_mismatch`](../../../../tests/unit/market_data/test_input_view_contract.py#L22)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_input_view_rejects_width_schema_mismatch() -> None:
    schema = InputSchema("market-input", "v1", "raw_market", ("close", "volume"))
    with pytest.raises(ValueError, match="schema width"):
        InputView(schema, "dataset-1", ((1.0,),))
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `InputView`

**Kind:** class · **Status:** stable · **Owner:** `features.contracts`

**Purpose:** Named view of values supplied to a model input.

**Exact API:** {py:obj}`features.contracts.InputView` · **Source:** [features/contracts.py:35](../../../../features/contracts.py#L35)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `test_distinct_input_representations_share_one_schema_contract`](../../../../tests/unit/market_data/test_input_view_contract.py#L15)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_distinct_input_representations_share_one_schema_contract(kind: InputKind) -> None:
    schema = InputSchema("market-input", "v1", kind, ("x0", "x1"))

    view = InputView(schema, "dataset-1", ((0.1, 0.2), (0.3, 0.4)))

    assert view.schema.kind == kind
    assert len(view.values) == 2
```

2. [test fixture: `test_input_view_rejects_width_schema_mismatch`](../../../../tests/unit/market_data/test_input_view_contract.py#L24)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_input_view_rejects_width_schema_mismatch() -> None:
    schema = InputSchema("market-input", "v1", "raw_market", ("close", "volume"))
    with pytest.raises(ValueError, match="schema width"):
        InputView(schema, "dataset-1", ((1.0,),))
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
