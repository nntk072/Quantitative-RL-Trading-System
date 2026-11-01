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

2. [test fixture: `test_device_capabilities_identify_rocm_backend`](../../../../tests/unit/compute/test_compute_contracts.py#L66)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 1)
    monkeypatch.setattr(torch.cuda, "get_device_properties", lambda _index: _Properties())
    monkeypatch.setattr(torch.cuda, "is_bf16_supported", lambda: True)

    capabilities = discover_device_capabilities("cuda:0")

    assert capabilities.accelerator_kind == "rocm"
    assert capabilities.accelerator_backend == "rocm"
    assert capabilities.device_name == "AMD Instinct MI210"
    assert capabilities.compute_capability == (9, 0)
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/engineering`
- Generated package reference: {doc}`../../generated/compute/index`
