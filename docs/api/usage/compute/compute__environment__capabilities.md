# Compute · `environment.capabilities`

This page contains 1 public callable records owned by `compute.environment.capabilities`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `discover_device_capabilities`

**Kind:** function · **Status:** stable · **Owner:** `compute.environment.capabilities`

**Purpose:** Describe the selected visible accelerator without exposing model policy.

**Exact API:** {py:obj}`compute.environment.capabilities.discover_device_capabilities` · **Source:** [compute/environment/capabilities.py:12](../../../../compute/environment/capabilities.py#L12)

**Inputs and outputs:**

- **Args:**

  ```text
  device_hint: Device hint used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of describe the selected visible accelerator without exposing model policy.
  ```

**Observed usage:**

1. [test fixture: `test_device_capabilities_are_backend_neutral`](../../../../tests/unit/compute/test_compute_contracts.py#L43)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_device_capabilities_are_backend_neutral() -> None:
    capabilities = discover_device_capabilities("cpu")

    assert capabilities.accelerator_kind is None
    assert capabilities.accelerator_count == 0
    assert capabilities.accelerator_memory_bytes is None
    assert capabilities.architecture
```

2. [test fixture: `test_device_capabilities_reject_invalid_hint_without_touching_accelerator`](../../../../tests/unit/compute/test_compute_contracts.py#L53)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_device_capabilities_reject_invalid_hint_without_touching_accelerator() -> None:
    with pytest.raises(ValueError, match="Invalid device value"):
        discover_device_capabilities("not-a-device")
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/engineering`
- Generated package reference: {doc}`../../generated/compute/index`
