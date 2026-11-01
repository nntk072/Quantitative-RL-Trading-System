# Models · `encoders.gru`

This page contains 2 public callable records owned by `models.encoders.gru`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `GRUEncoder`

**Kind:** class · **Status:** stable · **Owner:** `models.encoders.gru`

**Purpose:** GRU-based sequence encoder for RL.

**Exact API:** {py:obj}`models.encoders.gru.GRUEncoder` · **Source:** [models/encoders/gru.py:20](../../../../models/encoders/gru.py#L20)

**Inputs and outputs:**

- **Args:**

  ```text
  seq_len: Observation window length in bars.
  n_features: Number of input features per bar.
  latent_dim: Width of the encoded sequence representation.
  hidden_size: Width of the GRU hidden state.
  num_layers: Number of stacked GRU layers.
  dropout: Dropout probability between GRU layers when multiple layers are used.
  account_dim: Optional width of account inputs; inferred from the observation
      space when omitted.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = GRUEncoder(observation_space=..., seq_len=..., n_features=..., latent_dim=..., hidden_size=..., num_layers=..., dropout=..., account_dim=...)
```

**Lifecycle context:** GRU-based sequence encoder for RL.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `GRUEncoder.forward`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.gru`

**Purpose:** Encode sequence and account observations into one policy feature vector.

**Exact API:** {py:obj}`models.encoders.gru.GRUEncoder.forward` · **Source:** [models/encoders/gru.py:80](../../../../models/encoders/gru.py#L80)

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
instance = GRUEncoder(...)
result = instance.forward(observations=...)
```

**Lifecycle context:** This callable participates in `GRUEncoder`: GRU-based sequence encoder for RL. Related public lifecycle methods: {py:obj}`models.encoders.gru.GRUEncoder.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`
