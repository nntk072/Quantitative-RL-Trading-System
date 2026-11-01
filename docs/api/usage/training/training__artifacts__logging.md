# Training · `artifacts.logging`

This page contains 1 public callable records owned by `training.artifacts.logging`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `attach_run_log`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.logging`

**Purpose:** Mirror console logs into ``run_dir/train.log``.

**Exact API:** {py:obj}`training.artifacts.logging.attach_run_log` · **Source:** [training/artifacts/logging.py:11](../../../../training/artifacts/logging.py#L11)

**Inputs and outputs:**

- **Args:**

  ```text
  run_dir: Text or path value identifying the run dir.
  ```

- **Returns:**

  ```text
  Path returned by ``attach_run_log``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = attach_run_log(run_dir=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`
