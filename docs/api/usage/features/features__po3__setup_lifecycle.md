# Features · `po3.setup_lifecycle`

This page contains 1 public callable records owned by `features.po3.setup_lifecycle`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_po3_setup_lifecycle_ledger`

**Kind:** function · **Status:** stable · **Owner:** `features.po3.setup_lifecycle`

**Purpose:** Project PO3 state rows into setup-sequence lifecycle records.

**Exact API:** {py:obj}`features.po3.setup_lifecycle.build_po3_setup_lifecycle_ledger` · **Source:** [features/po3/setup_lifecycle.py:82](../../../../features/po3/setup_lifecycle.py#L82)

**Inputs and outputs:**

- **Args:**

  ```text
  state: Output frame from ``build_po3_ifvg_state``.
  ```

- **Returns:**

  ```text
  A chronologically ordered frame with one row per accepted setup and
  one row per rejected same-bar sweep conflict.
  ```

- **Raises:**

  ```text
  ValueError: If the index, required state columns, or setup sequence
      identifiers cannot support an unambiguous projection.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = build_po3_setup_lifecycle_ledger(state=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
