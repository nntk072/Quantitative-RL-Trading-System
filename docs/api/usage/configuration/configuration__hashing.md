# Configuration · `hashing`

This page contains 1 public callable records owned by `configuration.hashing`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `config_sha256`

**Kind:** function · **Status:** stable · **Owner:** `configuration.hashing`

**Purpose:** Hash the canonical representation of a configuration mapping.

**Exact API:** {py:obj}`configuration.hashing.config_sha256` · **Source:** [configuration/hashing.py:23](../../../../configuration/hashing.py#L23)

**Inputs and outputs:**

- **Args:**

  ```text
  config: Configuration values to serialize deterministically.
  ```

- **Returns:**

  ```text
  Lowercase SHA-256 hex digest.
  ```

**Observed usage:**

1. [test fixture: `test_configuration_serialization_and_repository_path_helpers`](../../../../tests/unit/configuration/test_configuration_helpers.py#L15)

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
