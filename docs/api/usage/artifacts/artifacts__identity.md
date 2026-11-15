# Artifacts · `identity`

This page contains 3 public callable records owned by `artifacts.identity`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ArtifactId`

**Kind:** class · **Status:** stable · **Owner:** `artifacts.identity`

**Purpose:** Stable content identity for one artifact and its semantic inputs.

**Exact API:** {py:obj}`artifacts.identity.ArtifactId` · **Source:** [artifacts/identity.py:11](../../../../artifacts/identity.py#L11)

**Inputs and outputs:**

**Observed usage:**

1. [production caller: `artifact_id`](../../../../artifacts/identity.py#L44)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def artifact_id(kind: str, semantic_inputs: Any) -> ArtifactId:
    payload = json.dumps(
        semantic_inputs, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return ArtifactId(kind, hashlib.sha256(payload).hexdigest())
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `artifact_id`

**Kind:** function · **Status:** stable · **Owner:** `artifacts.identity`

**Purpose:** Create a deterministic artifact identity from its kind and semantic inputs.

**Exact API:** {py:obj}`artifacts.identity.artifact_id` · **Source:** [artifacts/identity.py:31](../../../../artifacts/identity.py#L31)

**Inputs and outputs:**

- **Args:**

  ```text
  kind: Namespace identifying the artifact type.
  semantic_inputs: JSON-compatible values that determine artifact contents.
  ```

- **Returns:**

  ```text
  Identity containing the kind and canonical SHA-256 digest.
  ```

**Observed usage:**

1. [test fixture: `test_artifact_id_is_stable_for_mapping_order`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L19)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_artifact_id_is_stable_for_mapping_order() -> None:
    first = artifact_id("dataset", {"symbol": "US100", "timeframe": "M1"})
    second = artifact_id("dataset", {"timeframe": "M1", "symbol": "US100"})

    assert first == second
    assert isinstance(first, ArtifactId)
    assert str(first) == f"dataset:{first.digest}"
```

2. [tutorial example: `artifacts-evidence-lineage · code cell 2`](../../../../docs/subjects/E_evaluation_research/examples/artifacts-evidence-lineage.ipynb)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from artifacts.identity import artifact_id, file_sha256

inputs = {"schema": "example-v1", "rows": 2}
same_inputs = {"rows": 2, "schema": "example-v1"}
identity = artifact_id("synthetic-ledger", inputs)
assert identity == artifact_id("synthetic-ledger", same_inputs)
assert identity != artifact_id("synthetic-ledger", {**inputs, "rows": 3})

with TemporaryDirectory() as directory:
    payload = Path(directory) / "ledger.csv"
    payload.write_bytes(b"position,net_pnl\nA,4\nB,-1\n")
    original_digest = file_sha256(payload)
    lineage = {"artifact_id": str(identity), "sha256": original_digest}
    assert file_sha256(payload) == lineage["sha256"]

    payload.write_bytes(b"position,net_pnl\nA,4\nB,-2\n")
    assert file_sha256(payload) != lineage["sha256"]
    assert str(artifact_id("synthetic-ledger", inputs)) == lineage["artifact_id"]

print("Semantic ID:", lineage["artifact_id"])
print("Saved payload digest:", lineage["sha256"])
print("A subsequent payload change was detected.")
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `file_sha256`

**Kind:** function · **Status:** stable · **Owner:** `artifacts.identity`

**Purpose:** Hash file contents in bounded memory for artifact provenance.

**Exact API:** {py:obj}`artifacts.identity.file_sha256` · **Source:** [artifacts/identity.py:47](../../../../artifacts/identity.py#L47)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input file or directory.
  ```

- **Returns:**

  ```text
  Text returned by ``file_sha256``.
  ```

**Observed usage:**

1. [test fixture: `test_file_sha256_matches_standard_digest_for_empty_and_nonempty_files`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L36)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_file_sha256_matches_standard_digest_for_empty_and_nonempty_files(
    tmp_path: Path,
) -> None:
    payload = b"artifact bytes\x00with boundaries"
    nonempty = tmp_path / "payload.bin"
    empty = tmp_path / "empty.bin"
    nonempty.write_bytes(payload)
    empty.write_bytes(b"")

    assert file_sha256(nonempty) == hashlib.sha256(payload).hexdigest()
    assert file_sha256(empty) == hashlib.sha256(b"").hexdigest()
```

2. [test fixture: `test_evaluation_manifest_hashes_numerical_artifacts_and_parent_manifest`](../../../../tests/unit/evaluation/test_evaluation_manifest.py#L45)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "evaluation-artifacts-v1"
    assert manifest["partitions"] == ["training"]
    assert manifest["parent_manifests"]["run_manifest"]["sha256"] == file_sha256(parent_path)
    assert manifest["numerical_artifacts"] == [
        {"path": "training/metrics.json", "sha256": file_sha256(metrics_path)},
        {
            "path": "training/evaluation_diagnostics.json",
            "sha256": file_sha256(diagnostics_path),
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`
