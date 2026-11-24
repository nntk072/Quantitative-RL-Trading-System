# Models · `encoders.mtf`

This page contains 2 public callable records owned by `models.encoders.mtf`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `MTFEncoder`

**Kind:** class · **Status:** stable · **Owner:** `models.encoders.mtf`

**Purpose:** One causal TCN per configured timeframe window, fused to one latent.

**Exact API:** {py:obj}`models.encoders.mtf.MTFEncoder` · **Source:** [models/encoders/mtf.py:86](../../../../models/encoders/mtf.py#L86)

**Observed usage:**

1. [test fixture: `test_plain_mtf_batch_matches_each_row_alone`](../../../../tests/unit/models/test_mtf_masked_suffix.py#L63)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_plain_mtf_batch_matches_each_row_alone() -> None:
    torch.manual_seed(4)
    encoder = MTFEncoder(_space(), latent_dim=128, channels=(8, 8), dropout=0.0, account_dim=6)
    encoder.eval()
    obs = _observations()
    with torch.no_grad():
        batched = encoder(obs)
        for row in range(3):
            alone = encoder({k: v[row : row + 1] for k, v in obs.items()})
            assert torch.allclose(batched[row : row + 1], alone, atol=1e-5), row
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `MTFEncoder.forward`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.mtf`

**Purpose:** Encode aligned timeframe streams and account state into policy features.

**Exact API:** {py:obj}`models.encoders.mtf.MTFEncoder.forward` · **Source:** [models/encoders/mtf.py:140](../../../../models/encoders/mtf.py#L140)

**Inputs and outputs:**

- **Args:**

  ```text
  observations: Mapping of timeframe sequences, masks, and account values.
  ```

- **Returns:**

  ```text
  Fused timeframe latent concatenated with the account embedding.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MTFEncoder(...)
result = instance.forward(observations=...)
```

**Lifecycle context:** This callable participates in `MTFEncoder`: One causal TCN per configured timeframe window, fused to one latent. Related public lifecycle methods: {py:obj}`models.encoders.mtf.MTFEncoder.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`
