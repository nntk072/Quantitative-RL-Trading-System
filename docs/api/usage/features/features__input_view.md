# Features · `input_view`

This page contains 1 public callable records owned by `features.input_view`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `input_view_from_frame`

**Kind:** function · **Status:** stable · **Owner:** `features.input_view`

**Purpose:** Select declared columns from a tabular source without adding features.

**Exact API:** {py:obj}`features.input_view.input_view_from_frame` · **Source:** [features/input_view.py:10](../../../../features/input_view.py#L10)

**Inputs and outputs:**

- **Args:**

  ```text
  frame: Input data frame to process.
  dataset_id: Text or path value identifying the dataset id.
  schema: Schema used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of select declared columns from a tabular source without adding features.
  ```

**Observed usage:**

1. [test fixture: `test_input_view_from_frame_selects_declared_columns_and_rejects_missing_ones`](../../../../tests/unit/market_data/test_input_view_contract.py#L56)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_input_view_from_frame_selects_declared_columns_and_rejects_missing_ones() -> None:
    schema = InputSchema("bars", "v1", "raw_market", ("close", "volume"))
    frame = pd.DataFrame({"volume": [2, 3], "close": [100, 101], "unused": [9, 9]})

    view = input_view_from_frame(frame, dataset_id="fixture", schema=schema)

    assert view.values == ((100.0, 2.0), (101.0, 3.0))
    with pytest.raises(ValueError, match=r"missing schema columns: \['volume'\]"):
        input_view_from_frame(frame.drop(columns=["volume"]), dataset_id="fixture", schema=schema)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
