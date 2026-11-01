# Models · `encoders.tcn_regime`

This page contains 2 public callable records owned by `models.encoders.tcn_regime`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TCNRegimeEncoder`

**Kind:** class · **Status:** stable · **Owner:** `models.encoders.tcn_regime`

**Purpose:** Keep the established TCN/account path and fuse a masked D1 context MLP.

**Exact API:** {py:obj}`models.encoders.tcn_regime.TCNRegimeEncoder` · **Source:** [models/encoders/tcn_regime.py:15](../../../../models/encoders/tcn_regime.py#L15)

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TCNRegimeEncoder(observation_space=..., **kwargs)
```

**Lifecycle context:** Keep the established TCN/account path and fuse a masked D1 context MLP.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`

## `TCNRegimeEncoder.forward`

**Kind:** method · **Status:** stable · **Owner:** `models.encoders.tcn_regime`

**Purpose:** Encode temporal features together with the regime observation.

**Exact API:** {py:obj}`models.encoders.tcn_regime.TCNRegimeEncoder.forward` · **Source:** [models/encoders/tcn_regime.py:49](../../../../models/encoders/tcn_regime.py#L49)

**Inputs and outputs:**

- **Args:**

  ```text
  observations: Mapping containing sequence, account, regime, and regime-mask tensors.
  ```

- **Returns:**

  ```text
  Policy feature tensor combining sequence and regime context.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TCNRegimeEncoder(...)
result = instance.forward(observations=...)
```

**Lifecycle context:** This callable participates in `TCNRegimeEncoder`: Keep the established TCN/account path and fuse a masked D1 context MLP. Related public lifecycle methods: {py:obj}`models.encoders.tcn_regime.TCNRegimeEncoder.forward`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/models`
- Generated package reference: {doc}`../../generated/models/index`
