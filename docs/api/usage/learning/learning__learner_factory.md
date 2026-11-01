# Learning · `learner_factory`

This page contains 1 public callable records owned by `learning.learner_factory`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_learner`

**Kind:** function · **Status:** stable · **Owner:** `learning.learner_factory`

**Purpose:** Construct one supported learner backend behind the stable learner port.

**Exact API:** {py:obj}`learning.learner_factory.build_learner` · **Source:** [learning/learner_factory.py:10](../../../../learning/learner_factory.py#L10)

**Inputs and outputs:**

- **Args:**

  ```text
  backend: Text or path value identifying the backend.
  **options: Options used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of construct one supported learner backend behind the stable learner port.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = build_learner(backend=..., **options)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/learning/index`
