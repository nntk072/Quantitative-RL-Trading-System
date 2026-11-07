# Configuration · `paths`

This page contains 2 public callable records owned by `configuration.paths`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `RepositoryPaths`

**Kind:** class · **Status:** stable · **Owner:** `configuration.paths`

**Purpose:** Canonical repository locations derived from one root directory.

**Exact API:** {py:obj}`configuration.paths.RepositoryPaths` · **Source:** [configuration/paths.py:8](../../../../configuration/paths.py#L8)

**Inputs and outputs:**

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = RepositoryPaths(...)
```

**Lifecycle context:** Canonical repository locations derived from one root directory.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`

## `RepositoryPaths.from_root`

**Kind:** method · **Status:** stable · **Owner:** `configuration.paths`

**Purpose:** Resolve canonical repository paths beneath a root.

**Exact API:** {py:obj}`configuration.paths.RepositoryPaths.from_root` · **Source:** [configuration/paths.py:30](../../../../configuration/paths.py#L30)

**Inputs and outputs:**

- **Args:**

  ```text
  root: Repository directory to use as the path anchor.
  ```

- **Returns:**

  ```text
  Paths for configuration, data, cache, outputs, logs, and baselines.
  ```

**Observed usage:**

1. [test fixture: `test_configuration_serialization_and_repository_path_helpers`](../../../../tests/unit/configuration/test_configuration_helpers.py#L17)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_configuration_serialization_and_repository_path_helpers(tmp_path) -> None:
    config = {"b": 2, "a": 1}
    assert canonical_config_bytes(config) == b'{"a":1,"b":2}'
    assert len(config_sha256(config)) == 64

    paths = RepositoryPaths.from_root(tmp_path)
    assert paths.root == tmp_path.resolve()
    assert paths.outputs == tmp_path.resolve() / "outputs"
    with pytest.raises(FileNotFoundError, match="could not locate repository root"):
        repository_root(tmp_path)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/configuration`
- Generated package reference: {doc}`../../generated/configuration/index`
