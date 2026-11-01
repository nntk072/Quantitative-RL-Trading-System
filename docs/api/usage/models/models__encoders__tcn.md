# Models · `encoders.tcn`

This page contains 6 public callable records owned by `models.encoders.tcn`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `LegacyTCNEncoderV1`

**Kind:** class · **Status:** compatibility-only · **Owner:** `models.encoders.tcn`

**Purpose:** Archived Sep-2026 TCN layout retained for explicit 4D checkpoint migration.

**Exact API:** {py:obj}`models.encoders.tcn.LegacyTCNEncoderV1` · **Source:** [models/encoders/tcn.py:75](../../../../models/encoders/tcn.py#L75)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = LegacyTCNEncoderV1(observation_space=..., seq_len=..., n_features=..., latent_dim=..., channels=..., kernel_size=..., dropout=...)
```

**Lifecycle context:** Archived Sep-2026 TCN layout retained for explicit 4D checkpoint migration.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `TCNEncoder`

**Kind:** class · **Status:** stable · **Owner:** `models.encoders.tcn`

**Purpose:** Dilated causal TCN that maps a sequence window to a latent vector.

**Exact API:** {py:obj}`models.encoders.tcn.TCNEncoder` · **Source:** [models/encoders/tcn.py:141](../../../../models/encoders/tcn.py#L141)

**Inputs and outputs:**

- **Args:**

  ```text
  seq_len: Observation window length in bars.
  n_features: Number of input features per bar.
  latent_dim: Width of the encoded sequence representation.
  channels: Output width for each successive temporal convolution block.
  kernel_size: Width of each temporal convolution kernel.
  dropout: Dropout probability inside each temporal block.
  account_dim: Optional width of account inputs; inferred from the observation
      space when omitted.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TCNEncoder(observation_space=..., seq_len=..., n_features=..., latent_dim=..., channels=..., kernel_size=..., dropout=..., account_dim=...)
```

**Lifecycle context:** Dilated causal TCN that maps a sequence window to a latent vector.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `LegacyTCNEncoderV1`

**Kind:** class · **Status:** compatibility-only · **Owner:** `models.encoders.tcn`

**Purpose:** Archived Sep-2026 TCN layout retained for explicit 4D checkpoint migration.

**Exact API:** {py:obj}`models.encoders.tcn.LegacyTCNEncoderV1` · **Source:** [models/encoders/tcn.py:75](../../../../models/encoders/tcn.py#L75)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = LegacyTCNEncoderV1(observation_space=..., seq_len=..., n_features=..., latent_dim=..., channels=..., kernel_size=..., dropout=...)
```

**Lifecycle context:** Archived Sep-2026 TCN layout retained for explicit 4D checkpoint migration.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `LegacyTCNEncoderV1.forward`

**Kind:** method · **Status:** compatibility-only · **Owner:** `models.encoders.tcn`

**Purpose:** Encode the legacy sequence and account observation layout.

**Exact API:** {py:obj}`models.encoders.tcn.LegacyTCNEncoderV1.forward` · **Source:** [models/encoders/tcn.py:125](../../../../models/encoders/tcn.py#L125)

**Inputs and outputs:**

- **Args:**

  ```text
  observations: Mapping containing batched seq and account tensors.
  ```

- **Returns:**

  ```text
  Policy feature tensor in the checkpoint-compatible layout.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = LegacyTCNEncoderV1(...)
result = instance.forward(observations=...)
```

**Lifecycle context:** This callable participates in `LegacyTCNEncoderV1`: Archived Sep-2026 TCN layout retained for explicit 4D checkpoint migration. Related public lifecycle methods: {py:obj}`models.encoders.tcn.LegacyTCNEncoderV1.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `TCNEncoder.forward`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.tcn`

**Purpose:** Encode sequence and account observations with a temporal convolutional network.

**Exact API:** {py:obj}`models.encoders.tcn.TCNEncoder.forward` · **Source:** [models/encoders/tcn.py:209](../../../../models/encoders/tcn.py#L209)

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
instance = TCNEncoder(...)
result = instance.forward(observations=...)
```

**Lifecycle context:** This callable participates in `TCNEncoder`: Dilated causal TCN that maps a sequence window to a latent vector. Related public lifecycle methods: {py:obj}`models.encoders.tcn.TCNEncoder.receptive_field`, {py:obj}`models.encoders.tcn.TCNEncoder.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `TCNEncoder.receptive_field`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.tcn`

**Purpose:** Bars visible at the last step. Two kernel-sized convs per dilation.

**Exact API:** {py:obj}`models.encoders.tcn.TCNEncoder.receptive_field` · **Source:** [models/encoders/tcn.py:201](../../../../models/encoders/tcn.py#L201)

**Inputs and outputs:**

- **Returns:**

  ```text
  Numeric result returned by ``receptive_field``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TCNEncoder(...)
value = instance.receptive_field
```

**Lifecycle context:** This callable participates in `TCNEncoder`: Dilated causal TCN that maps a sequence window to a latent vector. Related public lifecycle methods: {py:obj}`models.encoders.tcn.TCNEncoder.receptive_field`, {py:obj}`models.encoders.tcn.TCNEncoder.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`
