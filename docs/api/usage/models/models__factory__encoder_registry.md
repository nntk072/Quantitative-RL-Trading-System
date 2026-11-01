# Models · `factory.encoder_registry`

This page contains 1 public callable records owned by `models.factory.encoder_registry`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `encoder_for`

**Kind:** function · **Status:** stable · **Owner:** `models.factory.encoder_registry`

**Purpose:** Resolve a declared encoder ID, failing closed for unknown names.

**Exact API:** {py:obj}`models.factory.encoder_registry.encoder_for` · **Source:** [models/factory/encoder_registry.py:38](../../../../models/factory/encoder_registry.py#L38)

**Inputs and outputs:**

- **Args:**

  ```text
  architecture: Text or path value identifying the architecture.
  ```

- **Returns:**

  ```text
  Result of resolve a declared encoder ID, failing closed for unknown names.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = encoder_for(architecture=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`
