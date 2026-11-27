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

**Observed usage:**

1. [test fixture: `test_experiment_run_package_entrypoint_delegates_to_controller`](../../../../tests/unit/experiments/test_experiment_run_artifacts.py#L1327)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        calls.append("main")
        return 0

    monkeypatch.setattr(execution, "main", main)

    assert run_experiment() == 0
    assert calls == ["main"]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/experiments/index`
