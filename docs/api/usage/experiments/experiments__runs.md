# Experiments · `runs`

This page contains 1 public callable records owned by `experiments.runs`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `run_experiment`

**Kind:** function · **Status:** stable · **Owner:** `experiments.runs`

**Purpose:** Run the experiment run controller through its canonical composition root.

**Exact API:** {py:obj}`experiments.runs.run_experiment` · **Source:** [experiments/runs/__init__.py:6](../../../../experiments/runs/__init__.py#L6)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``run_experiment``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = run_experiment()
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
