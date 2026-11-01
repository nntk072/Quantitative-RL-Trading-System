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

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = input_view_from_frame(frame=..., dataset_id=..., schema=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
