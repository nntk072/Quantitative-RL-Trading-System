# Models · `encoders.transformer`

This page contains 2 public callable records owned by `models.encoders.transformer`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TransformerEncoder`

**Kind:** class · **Status:** stable · **Owner:** `models.encoders.transformer`

**Purpose:** Causal Transformer encoder (standard PyTorch ``TransformerEncoderLayer``).

**Exact API:** {py:obj}`models.encoders.transformer.TransformerEncoder` · **Source:** [models/encoders/transformer.py:52](../../../../models/encoders/transformer.py#L52)

**Inputs and outputs:**

- **Args:**

  ```text
  seq_len: Maximum configured observation window in bars.
  n_features: Number of input features per bar.
  latent_dim: Width of the encoded sequence representation.
  d_model: Width of the Transformer token embeddings, divisible by ``nhead``.
  nhead: Number of attention heads per Transformer layer.
  num_layers: Number of stacked Transformer encoder layers.
  dim_feedforward: Width of the feed-forward network in each layer.
  dropout: Dropout probability used inside Transformer layers.
  account_dim: Optional width of account inputs; inferred from the observation
      space when omitted.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TransformerEncoder(observation_space=..., seq_len=..., n_features=..., latent_dim=..., d_model=..., nhead=..., num_layers=..., dim_feedforward=..., dropout=..., account_dim=...)
```

**Lifecycle context:** Causal Transformer encoder (standard PyTorch ``TransformerEncoderLayer``).

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `TransformerEncoder.forward`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.transformer`

**Purpose:** Encode sequence and account observations with self-attention.

**Exact API:** {py:obj}`models.encoders.transformer.TransformerEncoder.forward` · **Source:** [models/encoders/transformer.py:142](../../../../models/encoders/transformer.py#L142)

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
instance = TransformerEncoder(...)
result = instance.forward(observations=...)
```

**Lifecycle context:** This callable participates in `TransformerEncoder`: Causal Transformer encoder (standard PyTorch ``TransformerEncoderLayer``). Related public lifecycle methods: {py:obj}`models.encoders.transformer.TransformerEncoder.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`
