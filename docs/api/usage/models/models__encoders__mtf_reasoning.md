# Models · `encoders.mtf_reasoning`

This page contains 2 public callable records owned by `models.encoders.mtf_reasoning`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `MTFReasoningEncoder`

**Kind:** class · **Status:** stable · **Owner:** `models.encoders.mtf_reasoning`

**Purpose:** Preserve MTF's causal branches and add one learned cross-timeframe block.

**Exact API:** {py:obj}`models.encoders.mtf_reasoning.MTFReasoningEncoder` · **Source:** [models/encoders/mtf_reasoning.py:13](../../../../models/encoders/mtf_reasoning.py#L13)

**Observed usage:**

1. [test fixture: `test_efficient_encoders_reduce_parameters_and_keep_production_output_width`](../../../../tests/unit/models/test_mtf_efficient_encoders.py#L171)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_efficient_encoders_reduce_parameters_and_keep_production_output_width() -> None:
    baseline = MTFReasoningEncoder(
        _space(), latent_dim=16, channels=(8, 8), dropout=0.0, attention_heads=4
    )
    baseline_parameters = sum(parameter.numel() for parameter in baseline.parameters())
    for factory in _encoder_factories():
        encoder = factory()
        assert sum(parameter.numel() for parameter in encoder.parameters()) < baseline_parameters

# … caller assertions omitted …
```

2. [test fixture: `test_candidate_masks_are_history_independent_and_timeframe_scoped`](../../../../tests/unit/simulation/test_environment/test_trade_setup_observation.py#L138)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "channels": (4, 8),
        "attention_heads": 2,
        "feedforward_dim": 16,
        "dropout": 0.0,
    }
    b_encoder = MTFReasoningEncoder(b_env.observation_space, **encoder_kwargs)
    c_encoder = MTFReasoningEncoder(c_env.observation_space, **encoder_kwargs)
    assert sum(parameter.numel() for parameter in b_encoder.parameters()) == sum(
        parameter.numel() for parameter in c_encoder.parameters()
    )
    import torch
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `MTFReasoningEncoder.forward`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.mtf_reasoning`

**Purpose:** Encode available timeframe streams while respecting each stream's validity mask.

**Exact API:** {py:obj}`models.encoders.mtf_reasoning.MTFReasoningEncoder.forward` · **Source:** [models/encoders/mtf_reasoning.py:75](../../../../models/encoders/mtf_reasoning.py#L75)

**Inputs and outputs:**

- **Args:**

  ```text
  observations: Mapping of timeframe sequences, masks, and account tensors.
  ```

- **Returns:**

  ```text
  Fused latent representation with account context.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MTFReasoningEncoder(...)
result = instance.forward(observations=...)
```

**Lifecycle context:** This callable participates in `MTFReasoningEncoder`: Preserve MTF's causal branches and add one learned cross-timeframe block. Related public lifecycle methods: {py:obj}`models.encoders.mtf_reasoning.MTFReasoningEncoder.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`
