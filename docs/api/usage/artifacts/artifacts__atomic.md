# Artifacts · `atomic`

This page contains 2 public callable records owned by `artifacts.atomic`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `write_json_atomic`

**Kind:** function · **Status:** stable · **Owner:** `artifacts.atomic`

**Purpose:** Atomically serialize JSON using the repository's canonical formatting.

**Exact API:** {py:obj}`artifacts.atomic.write_json_atomic` · **Source:** [artifacts/atomic.py:75](../../../../artifacts/atomic.py#L75)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input file or directory.
  value: Value to process.
  default: Default used by the operation described above.
  new_file_mode: New file mode used by the operation described above.
  ```

- **Returns:**

  ```text
  Path returned by ``write_json_atomic``.
  ```

**Observed usage:**

1. [test fixture: `test_atomic_writers_create_parent_and_replace_content`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L160)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_atomic_writers_create_parent_and_replace_content(tmp_path: Path) -> None:
    text_path = tmp_path / "nested" / "report.txt"
    json_path = tmp_path / "nested" / "manifest.json"

    assert write_text_atomic(text_path, "complete\n") == text_path
    assert write_json_atomic(json_path, {"b": 2, "a": 1}) == json_path
    assert text_path.read_text(encoding="utf-8") == "complete\n"
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"a": 1, "b": 2}
```

2. [test fixture: `test_atomic_json_replacement_preserves_existing_permissions`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L170)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_atomic_json_replacement_preserves_existing_permissions(tmp_path: Path) -> None:
    path = tmp_path / "experiment_run.json"
    path.write_text('{"old": true}\n', encoding="utf-8")
    path.chmod(0o640)

    write_json_atomic(path, {"new": True})

    assert json.loads(path.read_text(encoding="utf-8")) == {"new": True}
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o640
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `write_text_atomic`

**Kind:** function · **Status:** stable · **Owner:** `artifacts.atomic`

**Purpose:** Write text by replacing the destination atomically.

**Exact API:** {py:obj}`artifacts.atomic.write_text_atomic` · **Source:** [artifacts/atomic.py:41](../../../../artifacts/atomic.py#L41)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Destination file.
  text: Complete text to write.
  encoding: Text encoding used for the temporary and destination files.
  new_file_mode: Optional permissions for a newly created destination.
  ```

- **Returns:**

  ```text
  Path returned by ``write_text_atomic``.
  ```

**Observed usage:**

1. [test fixture: `test_atomic_writers_create_parent_and_replace_content`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L159)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_atomic_writers_create_parent_and_replace_content(tmp_path: Path) -> None:
    text_path = tmp_path / "nested" / "report.txt"
    json_path = tmp_path / "nested" / "manifest.json"

    assert write_text_atomic(text_path, "complete\n") == text_path
    assert write_json_atomic(json_path, {"b": 2, "a": 1}) == json_path
    assert text_path.read_text(encoding="utf-8") == "complete\n"
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"a": 1, "b": 2}
```

2. [production caller: `write_json_atomic`](../../../../artifacts/atomic.py#L96)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def write_json_atomic(
    path: str | Path,
    value: Any,
    *,
    default: Callable[[Any], Any] | None = str,
    new_file_mode: int | None = None,
) -> Path:
    return write_text_atomic(
        path,
        json.dumps(value, indent=2, sort_keys=True, default=default) + "\n",
        new_file_mode=new_file_mode,
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`
