# Artifacts · `config_snapshot`

This page contains 1 public callable records owned by `artifacts.config_snapshot`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `write_config_snapshot`

**Kind:** function · **Status:** stable · **Owner:** `artifacts.config_snapshot`

**Purpose:** Write a resolved ``config.yaml`` once, rejecting identity rewrites.

**Exact API:** {py:obj}`artifacts.config_snapshot.write_config_snapshot` · **Source:** [artifacts/config_snapshot.py:13](../../../../artifacts/config_snapshot.py#L13)

**Inputs and outputs:**

- **Args:**

  ```text
  run_dir: Run dir used by the operation described above.
  config: Configuration values used by this operation.
  ```

- **Returns:**

  ```text
  Path returned by ``write_config_snapshot``.
  ```

**Observed usage:**

1. [production caller: `save_run`](../../../../evaluation/reporting/run_artifact_writer.py#L916)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    test_evaluated = test_result is not None and test_metrics is not None
    if development_only and test_evaluated:
        raise ValueError("development-only runs cannot write report-only test artifacts")

    if cfg is not None:
        write_config_snapshot(run_dir, cfg)

    if report_profile not in ("full", "experiment_run_fast"):
        raise ValueError(f"unknown report_profile: {report_profile}")
    # The fast profile affects presentation artifacts only. Every evaluation,
    # risk gate, trade, equity series, and mandatory report remains intact.
# … caller assertions omitted …
```

2. [production caller: `write_run_config_snapshot`](../../../../training/artifacts/snapshots.py#L19)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def write_run_config_snapshot(run_dir: str | Path, config: Any) -> Path:
    return write_config_snapshot(run_dir, config)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`
