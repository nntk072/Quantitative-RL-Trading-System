# Training · `artifacts.snapshots`

This page contains 1 public callable records owned by `training.artifacts.snapshots`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `write_run_config_snapshot`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.snapshots`

**Purpose:** Retain the training artifact API while sharing one snapshot writer.

**Exact API:** {py:obj}`training.artifacts.snapshots.write_run_config_snapshot` · **Source:** [training/artifacts/snapshots.py:9](../../../../training/artifacts/snapshots.py#L9)

**Inputs and outputs:**

- **Args:**

  ```text
  run_dir: Run dir used by the operation described above.
  config: Configuration values used by this operation.
  ```

- **Returns:**

  ```text
  Path returned by ``write_run_config_snapshot``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = write_run_config_snapshot(run_dir=..., config=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`
