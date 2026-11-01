# Compute · `environment.device`

This page contains 2 public callable records owned by `compute.environment.device`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `get_device`

**Kind:** function · **Status:** stable · **Owner:** `compute.environment.device`

**Purpose:** Resolve the torch device to use.

**Exact API:** {py:obj}`compute.environment.device.get_device` · **Source:** [compute/environment/device.py:31](../../../../compute/environment/device.py#L31)

**Inputs and outputs:**

- **Args:**

  ```text
  config_device: Optional device hint from config. Accepted values:

      * ``None`` or ``"auto"`` — pick CUDA if available, else CPU.
      * ``"cpu"``, ``"cuda"``, ``"cuda:0"``, ``"cuda:1"``, ... — use as-is.
      * Any other string raises ``ValueError``.
  ```

- **Returns:**

  ```text
  torch.device:
  ```

**Observed usage:**

1. [test fixture: `test_explicit_cpu`](../../../../tests/integration/test_device.py#L31)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_explicit_cpu(self) -> None:
    assert get_device("cpu").type == "cpu"
```

2. [test fixture: `test_invalid_raises`](../../../../tests/integration/test_device.py#L35)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_invalid_raises(self) -> None:
    with pytest.raises(ValueError, match="Invalid device"):
        get_device("not-a-device")
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/engineering`
- Generated package reference: {doc}`../../generated/compute/index`

## `scale_training_cfg`

**Kind:** function · **Status:** stable · **Owner:** `compute.environment.device`

**Purpose:** Mutate ``cfg`` in place with RAM/VRAM-aware PPO/SAC throughput settings.

**Exact API:** {py:obj}`compute.environment.device.scale_training_cfg` · **Source:** [compute/environment/device.py:174](../../../../compute/environment/device.py#L174)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  device: Compute device on which to perform the operation.
  arch: Text or path value identifying the arch.
  preserve_ppo_geometry: Whether to enable or require the preserve ppo geometry.
  ```

**Observed usage:**

1. [test fixture: `test_scale_training_cfg_cpu_keeps_n_envs`](../../../../tests/integration/test_device.py#L341)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "env": {"n_envs": 4},
            "ppo": {"n_steps": 2048, "batch_size": 256, "n_epochs": 10},
            "sac": {"batch_size": 256},
        }
    )
    scale_training_cfg(cfg, torch.device("cpu"), "transformer")
    assert int(cfg.env.n_envs) == 4
    assert int(cfg.ppo.batch_size) == 256
    assert int(cfg.ppo.n_epochs) == 10
```

2. [test fixture: `test_scale_training_cfg_preserves_configured_sac_batch_size`](../../../../tests/integration/test_device.py#L374)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "ppo": {"n_steps": 2048, "batch_size": 512, "n_epochs": 10},
            "sac": {"batch_size": 512},
        }
    )

    scale_training_cfg(cfg, torch.device("cuda:0"), "tcn")

    assert int(cfg.ppo.n_steps) == 8192
    assert int(cfg.ppo.batch_size) == 4096
    assert int(cfg.sac.batch_size) == 512
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/engineering`
- Generated package reference: {doc}`../../generated/compute/index`
