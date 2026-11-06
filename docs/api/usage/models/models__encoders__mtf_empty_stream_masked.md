# Models · `encoders.mtf_empty_stream_masked`

This page contains 2 public callable records owned by `models.encoders.mtf_empty_stream_masked`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `MTFEmptyStreamMaskedV1Encoder`

**Kind:** class · **Status:** stable · **Owner:** `models.encoders.mtf_empty_stream_masked`

**Purpose:** Preserve MTFEncoder's parameters while zeroing unavailable stream tokens.

**Exact API:** {py:obj}`models.encoders.mtf_empty_stream_masked.MTFEmptyStreamMaskedV1Encoder` · **Source:** [models/encoders/mtf_empty_stream_masked.py:10](../../../../models/encoders/mtf_empty_stream_masked.py#L10)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MTFEmptyStreamMaskedV1Encoder(...)
```

**Lifecycle context:** Preserve MTFEncoder's parameters while zeroing unavailable stream tokens.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `MTFEmptyStreamMaskedV1Encoder.forward`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.mtf_empty_stream_masked`

**Purpose:** Encode timeframe streams, excluding any stream with no valid rows.

**Exact API:** {py:obj}`models.encoders.mtf_empty_stream_masked.MTFEmptyStreamMaskedV1Encoder.forward` · **Source:** [models/encoders/mtf_empty_stream_masked.py:27](../../../../models/encoders/mtf_empty_stream_masked.py#L27)

**Inputs and outputs:**

- **Args:**

  ```text
  observations: Sequence, validity-mask, and account tensors keyed by stream.
  ```

- **Returns:**

  ```text
  Fused market latent concatenated with the encoded account state.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = MTFEmptyStreamMaskedV1Encoder(...)
result = instance.forward(observations=...)
```

**Lifecycle context:** This callable participates in `MTFEmptyStreamMaskedV1Encoder`: Preserve MTFEncoder's parameters while zeroing unavailable stream tokens. Related public lifecycle methods: {py:obj}`models.encoders.mtf_empty_stream_masked.MTFEmptyStreamMaskedV1Encoder.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`
