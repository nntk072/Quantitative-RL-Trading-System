# Artifacts · `manifest`

This page contains 3 public callable records owned by `artifacts.manifest`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ArtifactManifest`

**Kind:** class · **Status:** stable · **Owner:** `artifacts.manifest`

**Purpose:** Provenance and retention metadata associated with a stored artifact.

**Exact API:** {py:obj}`artifacts.manifest.ArtifactManifest` · **Source:** [artifacts/manifest.py:14](../../../../artifacts/manifest.py#L14)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `test_manifest_rejects_invalid_identity_fields`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L211)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_manifest_rejects_invalid_identity_fields(values, message) -> None:
    with pytest.raises(ValueError, match=message):
        ArtifactManifest(**values)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ArtifactManifest.read`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.manifest`

**Purpose:** Read and validate a manifest from disk.

**Exact API:** {py:obj}`artifacts.manifest.ArtifactManifest.read` · **Source:** [artifacts/manifest.py:61](../../../../artifacts/manifest.py#L61)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Manifest file to parse.
  ```

- **Returns:**

  ```text
  Parsed artifact manifest.
  ```

- **Raises:**

  ```text
  ValueError: The file does not contain a valid manifest mapping.
  ```

**Observed usage:**

1. [test fixture: `test_manifest_read_requires_a_mapping_root`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L219)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_manifest_read_requires_a_mapping_root(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="root must be a mapping"):
        ArtifactManifest.read(path)
```

2. [test fixture: `test_manifest_read_rejects_unknown_fields`](../../../../tests/unit/artifacts/test_artifact_lifecycle.py#L230)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_manifest_read_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"kind": "run", "artifact_id": "run:1", "unowned_field": True}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fields are invalid"):
        ArtifactManifest.read(path)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`

## `ArtifactManifest.to_dict`

**Kind:** method · **Status:** stable · **Owner:** `artifacts.manifest`

**Purpose:** Return the manifest as a JSON-compatible mapping.

**Exact API:** {py:obj}`artifacts.manifest.ArtifactManifest.to_dict` · **Source:** [artifacts/manifest.py:50](../../../../artifacts/manifest.py#L50)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = ArtifactManifest(...)
result = instance.to_dict()
```

**Lifecycle context:** This callable participates in `ArtifactManifest`: Provenance and retention metadata associated with a stored artifact. Related public lifecycle methods: {py:obj}`artifacts.manifest.ArtifactManifest.to_dict`, {py:obj}`artifacts.manifest.ArtifactManifest.read`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/workflows`
- Generated package reference: {doc}`../../generated/artifacts/index`
