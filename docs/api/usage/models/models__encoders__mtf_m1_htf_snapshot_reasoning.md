# Models · `encoders.mtf_m1_htf_snapshot_reasoning`

This page contains 3 public callable records owned by `models.encoders.mtf_m1_htf_snapshot_reasoning`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `M1TCNHTFSnapshotReasoningEncoder`

**Kind:** class · **Status:** stable · **Owner:** `models.encoders.mtf_m1_htf_snapshot_reasoning`

**Purpose:** Keep D's M1 TCN and encode only each HTF's latest valid feature row.

**Exact API:** {py:obj}`models.encoders.mtf_m1_htf_snapshot_reasoning.M1TCNHTFSnapshotReasoningEncoder` · **Source:** [models/encoders/mtf_m1_htf_snapshot_reasoning.py:19](../../../../models/encoders/mtf_m1_htf_snapshot_reasoning.py#L19)

**Observed usage:**

1. [test fixture: `_encoder_factories`](../../../../tests/unit/models/test_mtf_efficient_encoders.py#L69)

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

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `M1TCNHTFSnapshotReasoningEncoder.encoder_provenance`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.mtf_m1_htf_snapshot_reasoning`

**Purpose:** Return architecture identifiers and snapshot-stream details for checkpoint provenance.

**Exact API:** {py:obj}`models.encoders.mtf_m1_htf_snapshot_reasoning.M1TCNHTFSnapshotReasoningEncoder.encoder_provenance` · **Source:** [models/encoders/mtf_m1_htf_snapshot_reasoning.py:79](../../../../models/encoders/mtf_m1_htf_snapshot_reasoning.py#L79)

**Inputs and outputs:**

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``Any`` values.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = M1TCNHTFSnapshotReasoningEncoder(...)
value = instance.encoder_provenance
```

**Lifecycle context:** This callable participates in `M1TCNHTFSnapshotReasoningEncoder`: Keep D's M1 TCN and encode only each HTF's latest valid feature row. Related public lifecycle methods: {py:obj}`models.encoders.mtf_m1_htf_snapshot_reasoning.M1TCNHTFSnapshotReasoningEncoder.encoder_provenance`, {py:obj}`models.encoders.mtf_m1_htf_snapshot_reasoning.M1TCNHTFSnapshotReasoningEncoder.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `M1TCNHTFSnapshotReasoningEncoder.forward`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.mtf_m1_htf_snapshot_reasoning`

**Purpose:** Encode M1 history and aligned higher-timeframe snapshots.

**Exact API:** {py:obj}`models.encoders.mtf_m1_htf_snapshot_reasoning.M1TCNHTFSnapshotReasoningEncoder.forward` · **Source:** [models/encoders/mtf_m1_htf_snapshot_reasoning.py:97](../../../../models/encoders/mtf_m1_htf_snapshot_reasoning.py#L97)

**Inputs and outputs:**

- **Args:**

  ```text
  observations: Mapping of sequence, snapshot, mask, and account tensors.
  ```

- **Returns:**

  ```text
  Fused policy feature tensor for the observation batch.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = M1TCNHTFSnapshotReasoningEncoder(...)
result = instance.forward(observations=...)
```

**Lifecycle context:** This callable participates in `M1TCNHTFSnapshotReasoningEncoder`: Keep D's M1 TCN and encode only each HTF's latest valid feature row. Related public lifecycle methods: {py:obj}`models.encoders.mtf_m1_htf_snapshot_reasoning.M1TCNHTFSnapshotReasoningEncoder.encoder_provenance`, {py:obj}`models.encoders.mtf_m1_htf_snapshot_reasoning.M1TCNHTFSnapshotReasoningEncoder.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`
