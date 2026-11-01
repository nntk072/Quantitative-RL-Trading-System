# Compute · `environment.precision`

This page contains 4 public callable records owned by `compute.environment.precision`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `configure_accelerator_for_training`

**Kind:** function · **Status:** stable · **Owner:** `compute.environment.precision`

**Purpose:** Configure allocator and backend kernels before PPO's first GPU allocation.

**Exact API:** {py:obj}`compute.environment.precision.configure_accelerator_for_training` · **Source:** [compute/environment/precision.py:76](../../../../compute/environment/precision.py#L76)

**Inputs and outputs:**

- **Args:**

  ```text
  device_hint: Device hint used by the operation described above.
  cudnn_benchmark: Whether to enable or require the cudnn benchmark.
  ```

**Observed usage:**

1. [production caller: `configure_cuda_for_training`](../../../../compute/environment/precision.py#L114)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def configure_cuda_for_training(
    device_hint: str | torch.device | None = None, *, cudnn_benchmark: bool = True
) -> None:
    configure_accelerator_for_training(device_hint, cudnn_benchmark=cudnn_benchmark)
```

2. [production caller: `_prepare_training_configuration`](../../../../training/runner/configuration_stage.py#L38)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "Walk-forward with an externally fitted VAE has unverified fold provenance; "
            "provide a fold-scoped VAE fitting pipeline before enabling this combination"
        )

    cfg = load_merged_config(args)
    configure_accelerator_for_training(
        cfg.get("device"),
        cudnn_benchmark=bool(cfg.get("compute", {}).get("cudnn_benchmark", True)),
    )
    _setup_rngs(args.seed)
    try:
        _validate_q5_resume_state(cfg, resume_checkpoint=args.resume_checkpoint)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/engineering`
- Generated package reference: {doc}`../../generated/compute/index`

## `configure_cuda_for_training`

**Kind:** function · **Status:** stable · **Owner:** `compute.environment.precision`

**Purpose:** Backward-compatible alias for accelerator-wide training setup.

**Exact API:** {py:obj}`compute.environment.precision.configure_cuda_for_training` · **Source:** [compute/environment/precision.py:105](../../../../compute/environment/precision.py#L105)

**Inputs and outputs:**

- **Args:**

  ```text
  device_hint: Device hint used by the operation described above.
  cudnn_benchmark: Whether to enable or require the cudnn benchmark.
  ```

**Observed usage:**

1. [test fixture: `test_configure_cuda_for_training_is_noop_safe`](../../../../tests/integration/test_device.py#L205)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_configure_cuda_for_training_is_noop_safe() -> None:
    configure_cuda_for_training()
```

2. [test fixture: `test_configure_cuda_enables_nvidia_tf32_and_allocator`](../../../../tests/integration/test_device.py#L285)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            supports_bfloat16=True,
            accelerator_backend="cuda",
            compute_capability=(8, 0),
        ),
    )
    configure_cuda_for_training(cudnn_benchmark=cudnn_benchmark)
    assert __import__("os").environ["PYTORCH_CUDA_ALLOC_CONF"] == "expandable_segments:True"
    assert cuda_matmul.allow_tf32 is True
    assert cudnn.allow_tf32 is True
    assert cudnn.benchmark is cudnn_benchmark
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/engineering`
- Generated package reference: {doc}`../../generated/compute/index`

## `get_autocast_context`

**Kind:** function · **Status:** stable · **Owner:** `compute.environment.precision`

**Purpose:** Return the selected accelerator autocast context, or a CPU no-op.

**Exact API:** {py:obj}`compute.environment.precision.get_autocast_context` · **Source:** [compute/environment/precision.py:51](../../../../compute/environment/precision.py#L51)

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

1. [test fixture: `test_autocast_is_a_noop_on_cpu`](../../../../tests/integration/test_device.py#L212)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_autocast_is_a_noop_on_cpu() -> None:
    import torch

    assert get_autocast_dtype("cpu") is None
    with get_autocast_context("cpu"):
        assert not torch.is_autocast_enabled("cpu")
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/engineering`
- Generated package reference: {doc}`../../generated/compute/index`

## `get_autocast_dtype`

**Kind:** function · **Status:** stable · **Owner:** `compute.environment.precision`

**Purpose:** Choose fp16 for pre-Ampere GPUs and bf16 when a newer GPU supports it.

**Exact API:** {py:obj}`compute.environment.precision.get_autocast_dtype` · **Source:** [compute/environment/precision.py:31](../../../../compute/environment/precision.py#L31)

**Inputs and outputs:**

- **Args:**

  ```text
  device: Compute device on which to perform the operation.
  ```

- **Returns:**

  ```text
  Result of choose fp16 for pre-Ampere GPUs and bf16 when a newer GPU supports it.
  ```

**Observed usage:**

1. [test fixture: `test_autocast_is_a_noop_on_cpu`](../../../../tests/integration/test_device.py#L211)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_autocast_is_a_noop_on_cpu() -> None:
    import torch

    assert get_autocast_dtype("cpu") is None
    with get_autocast_context("cpu"):
        assert not torch.is_autocast_enabled("cpu")
```

2. [test fixture: `test_autocast_dtype_tracks_device_capabilities`](../../../../tests/integration/test_device.py#L250)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            accelerator_memory_bytes=None,
            supports_bfloat16=supports_bfloat16,
            compute_capability=capability,
        ),
    )
    assert str(get_autocast_dtype("cuda:0")) == expected
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/engineering`
- Generated package reference: {doc}`../../generated/compute/index`
