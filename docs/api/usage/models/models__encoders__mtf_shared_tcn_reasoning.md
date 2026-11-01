# Models · `encoders.mtf_shared_tcn_reasoning`

This page contains 3 public callable records owned by `models.encoders.mtf_shared_tcn_reasoning`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `SharedTCNMTFReasoningEncoder`

**Kind:** class · **Status:** stable · **Owner:** `models.encoders.mtf_shared_tcn_reasoning`

**Purpose:** One shared causal TCN processes all nine timeframe streams.

**Exact API:** {py:obj}`models.encoders.mtf_shared_tcn_reasoning.SharedTCNMTFReasoningEncoder` · **Source:** [models/encoders/mtf_shared_tcn_reasoning.py:77](../../../../models/encoders/mtf_shared_tcn_reasoning.py#L77)

**Observed usage:**

1. [test fixture: `_encoder_factories`](../../../../tests/unit/models/test_mtf_efficient_encoders.py#L67)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _encoder_factories() -> tuple[Callable[[], Any], ...]:
    common: dict[str, Any] = {
        "channels": (8, 8),
        "dropout": 0.0,
        "attention_heads": 4,
        "feedforward_dim": 32,
    }
    return (
        lambda: SharedTCNMTFReasoningEncoder(_space(), latent_dim=16, adapter_dim=5, **common),
        lambda: M1TCNHTFLiteReasoningEncoder(_space(), latent_dim=16, adapter_dim=4, **common),
        lambda: M1TCNHTFSnapshotReasoningEncoder(_space(), latent_dim=16, adapter_dim=4, **common),
    )
```

2. [test fixture: `test_shared_tcn_uses_one_temporal_core_for_all_nine_streams`](../../../../tests/unit/models/test_mtf_efficient_encoders.py#L127)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_shared_tcn_uses_one_temporal_core_for_all_nine_streams() -> None:
    encoder = SharedTCNMTFReasoningEncoder(
        _space(),
        latent_dim=16,
        channels=(8, 8),
        dropout=0.0,
        attention_heads=4,
        feedforward_dim=32,
        adapter_dim=5,
    )

    assert encoder.branch_count == 9
    assert len(encoder.adapters) == 9
    assert encoder.shared_core is True
    assert sum(1 for module in encoder.modules() if module is encoder.temporal_core) == 1
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `SharedTCNMTFReasoningEncoder.encoder_provenance`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.mtf_shared_tcn_reasoning`

**Purpose:** Return the shared encoder architecture and stream map for checkpoint provenance.

**Exact API:** {py:obj}`models.encoders.mtf_shared_tcn_reasoning.SharedTCNMTFReasoningEncoder.encoder_provenance` · **Source:** [models/encoders/mtf_shared_tcn_reasoning.py:131](../../../../models/encoders/mtf_shared_tcn_reasoning.py#L131)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Observed usage:**

1. [test fixture: `test_efficient_mtf_encoders_have_nine_tokens_finite_gradients_and_provenance`](../../../../tests/unit/models/test_mtf_efficient_encoders.py#L86)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    output.square().mean().backward()
    assert all(
        parameter.grad is None or torch.isfinite(parameter.grad).all()
        for parameter in encoder.parameters()
    )
    provenance = encoder.encoder_provenance
    assert provenance["branch_count"] == 9
    assert provenance["token_dim"] == 16
    assert provenance["latent_dim"] == 16
    assert provenance["attention_heads"] == 4
    assert provenance["attention_feedforward_dim"] == 32
```

2. [test fixture: `test_shared_tcn_uses_one_temporal_core_for_all_nine_streams`](../../../../tests/unit/models/test_mtf_efficient_encoders.py#L141)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    assert encoder.branch_count == 9
    assert len(encoder.adapters) == 9
    assert encoder.shared_core is True
    assert sum(1 for module in encoder.modules() if module is encoder.temporal_core) == 1
    assert encoder.encoder_provenance["htf_summary_type"] == "shared_causal_tcn"
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `SharedTCNMTFReasoningEncoder.forward`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.mtf_shared_tcn_reasoning`

**Purpose:** Encode multiple timeframe streams with a shared temporal convolution.

**Exact API:** {py:obj}`models.encoders.mtf_shared_tcn_reasoning.SharedTCNMTFReasoningEncoder.forward` · **Source:** [models/encoders/mtf_shared_tcn_reasoning.py:149](../../../../models/encoders/mtf_shared_tcn_reasoning.py#L149)

**Inputs and outputs:**

- **Args:**

  ```text
  observations: Mapping of stream sequences, masks, and account tensors.
  ```

- **Returns:**

  ```text
  Fused latent representation with account context.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = SharedTCNMTFReasoningEncoder(...)
result = instance.forward(observations=...)
```

**Lifecycle context:** This callable participates in `SharedTCNMTFReasoningEncoder`: One shared causal TCN processes all nine timeframe streams. Related public lifecycle methods: {py:obj}`models.encoders.mtf_shared_tcn_reasoning.SharedTCNMTFReasoningEncoder.encoder_provenance`, {py:obj}`models.encoders.mtf_shared_tcn_reasoning.SharedTCNMTFReasoningEncoder.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`
