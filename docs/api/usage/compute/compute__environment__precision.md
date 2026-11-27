# Compute · `environment.precision`

This page contains 4 public callable records owned by `compute.environment.precision`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `configure_accelerator_for_training`

**Kind:** function · **Status:** stable · **Owner:** `compute.environment.precision`

**Purpose:** Configure allocator and backend kernels before PPO's first GPU allocation.

**Exact API:** {py:obj}`compute.environment.precision.configure_accelerator_for_training` · **Source:** [compute/environment/precision.py:93](../../../../compute/environment/precision.py#L93)

**Inputs and outputs:**

- **Args:**

  ```text
  device_hint: Device hint used by the operation described above.
  cudnn_benchmark: Whether to enable or require the cudnn benchmark.
  ```

**Observed usage:**

1. [test fixture: `test_cpu_accelerator_setup_is_an_early_noop`](../../../../tests/integration/test_device.py#L218)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_cpu_accelerator_setup_is_an_early_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    import torch

    from compute.environment import precision

    monkeypatch.delenv("PYTORCH_CUDA_ALLOC_CONF", raising=False)
    monkeypatch.setattr(precision, "discover_device_capabilities", lambda _device: pytest.fail())

    configure_accelerator_for_training(torch.device("cpu"))
    configure_cuda_for_training("cpu")

    assert "PYTORCH_CUDA_ALLOC_CONF" not in __import__("os").environ
```

2. [production caller: `configure_cuda_for_training`](../../../../compute/environment/precision.py#L132)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def configure_cuda_for_training(
    device_hint: str | torch.device | None = None, *, cudnn_benchmark: bool = True
) -> None:
    configure_accelerator_for_training(device_hint, cudnn_benchmark=cudnn_benchmark)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/engineering`
- Generated package reference: {doc}`../../generated/compute/index`

## `configure_cuda_for_training`

**Kind:** function · **Status:** stable · **Owner:** `compute.environment.precision`

**Purpose:** Backward-compatible alias for accelerator-wide training setup.

**Exact API:** {py:obj}`compute.environment.precision.configure_cuda_for_training` · **Source:** [compute/environment/precision.py:123](../../../../compute/environment/precision.py#L123)

**Inputs and outputs:**

- **Args:**

  ```text
  device_hint: Device hint used by the operation described above.
  cudnn_benchmark: Whether to enable or require the cudnn benchmark.
  ```

**Observed usage:**

1. [test fixture: `test_configure_cuda_for_training_is_noop_safe`](../../../../tests/integration/test_device.py#L207)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_configure_cuda_for_training_is_noop_safe() -> None:
    configure_cuda_for_training()
```

2. [test fixture: `test_cpu_accelerator_setup_is_an_early_noop`](../../../../tests/integration/test_device.py#L219)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_cpu_accelerator_setup_is_an_early_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    import torch

    from compute.environment import precision

    monkeypatch.delenv("PYTORCH_CUDA_ALLOC_CONF", raising=False)
    monkeypatch.setattr(precision, "discover_device_capabilities", lambda _device: pytest.fail())

    configure_accelerator_for_training(torch.device("cpu"))
    configure_cuda_for_training("cpu")

    assert "PYTORCH_CUDA_ALLOC_CONF" not in __import__("os").environ
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/engineering`
- Generated package reference: {doc}`../../generated/compute/index`

## `get_autocast_context`

**Kind:** function · **Status:** stable · **Owner:** `compute.environment.precision`

**Purpose:** Return the selected accelerator autocast context, or a CPU no-op.

**Exact API:** {py:obj}`compute.environment.precision.get_autocast_context` · **Source:** [compute/environment/precision.py:68](../../../../compute/environment/precision.py#L68)

**Inputs and outputs:**

- **Args:**

  ```text
  device: Compute device on which to perform the operation.
  dtype: Dtype used by the operation described above.
  enabled: Enabled used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of return the selected accelerator autocast context, or a CPU no-op.
  ```

**Observed usage:**

1. [test fixture: `test_autocast_is_a_noop_on_cpu`](../../../../tests/integration/test_device.py#L228)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_autocast_is_a_noop_on_cpu() -> None:
    import torch

    assert get_autocast_dtype("cpu") is None
    with get_autocast_context("cpu"):
        assert not torch.is_autocast_enabled("cpu")
```

2. [test fixture: `test_autocast_context_can_be_disabled_on_visible_cuda`](../../../../tests/integration/test_device.py#L277)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_autocast_context_can_be_disabled_on_visible_cuda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch, "autocast", lambda **_kwargs: pytest.fail("autocast should be off"))

    with get_autocast_context("cuda:0", enabled=False):
        assert True
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/engineering`
- Generated package reference: {doc}`../../generated/compute/index`

## `get_autocast_dtype`

**Kind:** function · **Status:** stable · **Owner:** `compute.environment.precision`

**Purpose:** Choose the encoder autocast dtype for a CUDA device.

**Exact API:** {py:obj}`compute.environment.precision.get_autocast_dtype` · **Source:** [compute/environment/precision.py:31](../../../../compute/environment/precision.py#L31)

**Inputs and outputs:**

- **Args:**

  ```text
  device: Compute device on which to perform the operation.
  override: One of auto, fp16, bf16, fp32.
  ```

- **Returns:**

  ```text
  The autocast dtype, or None for no autocast.
  ```

**Observed usage:**

1. [test fixture: `test_autocast_is_a_noop_on_cpu`](../../../../tests/integration/test_device.py#L227)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_autocast_is_a_noop_on_cpu() -> None:
    import torch

    assert get_autocast_dtype("cpu") is None
    with get_autocast_context("cpu"):
        assert not torch.is_autocast_enabled("cpu")
```

2. [test fixture: `test_autocast_explicit_dtype_overrides`](../../../../tests/integration/test_device.py#L256)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        precision,
        "discover_device_capabilities",
        lambda _device: pytest.fail("explicit dtype must bypass capability discovery"),
    )

    chosen = get_autocast_dtype("cuda:0", override=override)

    actual = None if chosen is None else str(chosen)
    assert actual == expected
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/engineering`
- Generated package reference: {doc}`../../generated/compute/index`
