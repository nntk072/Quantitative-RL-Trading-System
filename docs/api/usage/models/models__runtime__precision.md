# Models · `runtime.precision`

This page contains 1 public callable records owned by `models.runtime.precision`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `enable_extractor_autocast`

**Kind:** function · **Status:** stable · **Owner:** `models.runtime.precision`

**Purpose:** Apply a caller-selected autocast dtype to an encoder; return fp32 features.

**Exact API:** {py:obj}`models.runtime.precision.enable_extractor_autocast` · **Source:** [models/runtime/precision.py:13](../../../../models/runtime/precision.py#L13)

**Inputs and outputs:**

- **Args:**

  ```text
  extractor: Extractor used by the operation described above.
  dtype: Dtype used by the operation described above.
  ```

**Observed usage:**

1. [test fixture: `test_enable_extractor_autocast_skips_transformer`](../../../../tests/integration/test_device.py#L472)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        d_model=16,
        nhead=2,
        num_layers=1,
        dim_feedforward=32,
    )
    enable_extractor_autocast(encoder, torch.bfloat16)
    assert getattr(encoder, "_amp_wrapped", False) is False
```

2. [production caller: `_finalize_cuda_policy`](../../../../learning/rl/agent.py#L894)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    seen_extractors: set[int] = set()
    for extractor in extractors:
        if extractor is None or id(extractor) in seen_extractors:
            continue
        seen_extractors.add(id(extractor))
        enable_extractor_autocast(extractor, autocast_dtype)
    return model
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`
