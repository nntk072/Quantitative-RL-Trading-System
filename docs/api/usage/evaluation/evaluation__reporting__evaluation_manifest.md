# Evaluation · `reporting.evaluation_manifest`

This page contains 2 public callable records owned by `evaluation.reporting.evaluation_manifest`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_evaluation_manifest`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.evaluation_manifest`

**Purpose:** Describe an evaluation bundle and connect it to its source artifacts.

**Exact API:** {py:obj}`evaluation.reporting.evaluation_manifest.build_evaluation_manifest` · **Source:** [evaluation/reporting/evaluation_manifest.py:14](../../../../evaluation/reporting/evaluation_manifest.py#L14)

**Inputs and outputs:**

- **Args:**

  ```text
  run_dir: Text or path value identifying the run dir.
  lineage: Key-value data used for the lineage.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_evaluation_manifest_hashes_numerical_artifacts_and_parent_manifest`](../../../../tests/unit/evaluation/test_evaluation_manifest.py#L42)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    ]
    assert manifest["lineage"] == {
        "checkpoint_sha256": "abc123",
        "source_run": "source-run",
    }
    assert build_evaluation_manifest(tmp_path) == {
        **manifest,
        "lineage": {},
    }
```

2. [production caller: `write_evaluation_manifest`](../../../../evaluation/reporting/evaluation_manifest.py#L88)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def write_evaluation_manifest(
    run_dir: Path,
    *,
    lineage: dict[str, Any] | None = None,
) -> Path:
    path = run_dir / "evaluation_manifest.json"
    write_json_atomic(path, build_evaluation_manifest(run_dir, lineage=lineage), default=None)
    return path
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`

## `write_evaluation_manifest`

**Kind:** function · **Status:** stable · **Owner:** `evaluation.reporting.evaluation_manifest`

**Purpose:** Atomically refresh the canonical evaluation provenance manifest.

**Exact API:** {py:obj}`evaluation.reporting.evaluation_manifest.write_evaluation_manifest` · **Source:** [evaluation/reporting/evaluation_manifest.py:73](../../../../evaluation/reporting/evaluation_manifest.py#L73)

**Inputs and outputs:**

- **Args:**

  ```text
  run_dir: Text or path value identifying the run dir.
  lineage: Key-value data used for the lineage.
  ```

- **Returns:**

  ```text
  Path returned by ``write_evaluation_manifest``.
  ```

**Observed usage:**

1. [test fixture: `test_evaluation_manifest_hashes_numerical_artifacts_and_parent_manifest`](../../../../tests/unit/evaluation/test_evaluation_manifest.py#L26)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    metrics_path = training / "metrics.json"
    metrics_path.write_text('{"total_return_pct": 2.5}\n', encoding="utf-8")
    parent_path = tmp_path / "run_manifest.json"
    parent_path.write_text('{"schema_version": 1}\n', encoding="utf-8")

    manifest_path = write_evaluation_manifest(
        tmp_path,
        lineage={"checkpoint_sha256": "abc123", "source_run": "source-run"},
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "evaluation-artifacts-v1"
    assert manifest["partitions"] == ["training"]
    assert manifest["parent_manifests"]["run_manifest"]["sha256"] == file_sha256(parent_path)
# … caller assertions omitted …
```

2. [production caller: `main`](../../../../evaluation/reanalysis/checkpoint_reanalysis.py#L1073)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    from evaluation.reporting.evaluation_manifest import write_evaluation_manifest

    source_manifest_hash = (
        file_sha256(source_manifest_path) if source_manifest_path.is_file() else None
    )
    write_evaluation_manifest(
        output_dir,
        lineage={
            "source_run": str(run_dir.resolve()),
            "source_run_manifest_sha256": source_manifest_hash,
            "checkpoint_sha256": file_sha256(ckpt_path),
            "dataset_parity_disposition": dataset_parity_disposition,
            "historical_holdout_inspected": True,
        },
    )
    log.info("Done. Reanalysis artifacts written to: %s", output_dir)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/evaluation/index`
