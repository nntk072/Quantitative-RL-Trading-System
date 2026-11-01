# Training · `artifacts.evaluation_result_writer`

This page contains 1 public callable records owned by `training.artifacts.evaluation_result_writer`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `write_evaluation_artifacts`

**Kind:** function · **Status:** stable · **Owner:** `training.artifacts.evaluation_result_writer`

**Purpose:** Write an explicit train/test evaluation report with unambiguous roles.

**Exact API:** {py:obj}`training.artifacts.evaluation_result_writer.write_evaluation_artifacts` · **Source:** [training/artifacts/evaluation_result_writer.py:14](../../../../training/artifacts/evaluation_result_writer.py#L14)

**Inputs and outputs:**

- **Args:**

  ```text
  run_dir: Text or path value identifying the run dir.
  seed: Random seed used to make sampling reproducible.
  completed_timesteps: Numeric value used for the completed timesteps.
  train_result: Key-value data used for the train result.
  test_result: Key-value data used for the test result.
  train_metrics: Train metrics used by the operation described above.
  test_metrics: Test metrics used by the operation described above.
  train_gate: Key-value data used for the train gate.
  train_activity_gate: Key-value data used for the train activity gate.
  account_currency: Text or path value identifying the account currency.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = write_evaluation_artifacts(run_dir=..., seed=..., completed_timesteps=..., train_result=..., test_result=..., train_metrics=..., test_metrics=..., train_gate=..., train_activity_gate=..., account_currency=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/training/index`
