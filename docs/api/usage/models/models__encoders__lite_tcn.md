# Models · `encoders.lite_tcn`

This page contains 3 public callable records owned by `models.encoders.lite_tcn`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `LiteTCNEncoder`

**Kind:** class · **Status:** stable · **Owner:** `models.encoders.lite_tcn`

**Purpose:** Compact causal depthwise-separable TCN with the standard 160-wide output.

**Exact API:** {py:obj}`models.encoders.lite_tcn.LiteTCNEncoder` · **Source:** [models/encoders/lite_tcn.py:95](../../../../models/encoders/lite_tcn.py#L95)

**Observed usage:**

1. [test fixture: `test_lite_tcn_rejects_empty_or_nonpositive_convolution_parameters`](../../../../tests/unit/models/test_mtf_efficient_encoders.py#L337)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_lite_tcn_rejects_empty_or_nonpositive_convolution_parameters(
    kwargs: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="LiteTCN"):
        LiteTCNEncoder(_space(), **kwargs)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `LiteTCNEncoder.forward`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.lite_tcn`

**Purpose:** Encode sequence and account observations with the lightweight temporal convolution.

**Exact API:** {py:obj}`models.encoders.lite_tcn.LiteTCNEncoder.forward` · **Source:** [models/encoders/lite_tcn.py:171](../../../../models/encoders/lite_tcn.py#L171)

**Inputs and outputs:**

- **Args:**

  ```text
  observations: Mapping containing batched seq and account tensors, plus optional valid-length metadata.
  ```

- **Returns:**

  ```text
  Concatenated latent sequence representation and account embedding.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = LiteTCNEncoder(...)
result = instance.forward(observations=...)
```

**Lifecycle context:** This callable participates in `LiteTCNEncoder`: Compact causal depthwise-separable TCN with the standard 160-wide output. Related public lifecycle methods: {py:obj}`models.encoders.lite_tcn.LiteTCNEncoder.receptive_field`, {py:obj}`models.encoders.lite_tcn.LiteTCNEncoder.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `LiteTCNEncoder.receptive_field`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.lite_tcn`

**Purpose:** Return the number of input bars visible at a block's last timestep.

**Exact API:** {py:obj}`models.encoders.lite_tcn.LiteTCNEncoder.receptive_field` · **Source:** [models/encoders/lite_tcn.py:149](../../../../models/encoders/lite_tcn.py#L149)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``receptive_field``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = LiteTCNEncoder(...)
value = instance.receptive_field
```

**Lifecycle context:** This callable participates in `LiteTCNEncoder`: Compact causal depthwise-separable TCN with the standard 160-wide output. Related public lifecycle methods: {py:obj}`models.encoders.lite_tcn.LiteTCNEncoder.receptive_field`, {py:obj}`models.encoders.lite_tcn.LiteTCNEncoder.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`
