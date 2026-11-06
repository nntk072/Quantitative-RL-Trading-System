# Features · `pipeline.session_context_features`

This page contains 2 public callable records owned by `features.pipeline.session_context_features`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `ensure_london_atr_distances`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.session_context_features`

**Purpose:** Add London ATR distances when the PD-context pair is absent.

**Exact API:** {py:obj}`features.pipeline.session_context_features.ensure_london_atr_distances` · **Source:** [features/pipeline/session_context_features.py:8](../../../../features/pipeline/session_context_features.py#L8)

**Inputs and outputs:**

- **Args:**

  ```text
  feat: Tabular data used for the feat.
  close: Tabular data used for the close.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``ensure_london_atr_distances``.
  ```

**Observed usage:**

1. [production caller: `build_features`](../../../../features/pipeline/feature_matrix_builder.py#L778)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    if need_trader_ctx:
        trader_ctx = build_trader_context_features(feat)
        for col in trader_ctx.columns:
            feat[col] = trader_ctx[col]

    feat = ensure_london_atr_distances(feat, primary["close"])
    # Retain decision price for opt-in setup-entry gating but exclude it from
    # the model observation sequence.
    if feat_cfg is not None and bool(getattr(feat_cfg, "include_previous_session_pd", False)):
        feat["decision_close"] = primary["close"].reindex(feat.index)
    session = OmegaConf.select(cfg, "session") if cfg is not None else None
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `ensure_london_atr_distances`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.session_context_features`

**Purpose:** Add London ATR distances when the PD-context pair is absent.

**Exact API:** {py:obj}`features.pipeline.session_context_features.ensure_london_atr_distances` · **Source:** [features/pipeline/session_context_features.py:8](../../../../features/pipeline/session_context_features.py#L8)

**Inputs and outputs:**

- **Args:**

  ```text
  feat: Tabular data used for the feat.
  close: Tabular data used for the close.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``ensure_london_atr_distances``.
  ```

**Observed usage:**

1. [production caller: `build_features`](../../../../features/pipeline/feature_matrix_builder.py#L778)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    if need_trader_ctx:
        trader_ctx = build_trader_context_features(feat)
        for col in trader_ctx.columns:
            feat[col] = trader_ctx[col]

    feat = ensure_london_atr_distances(feat, primary["close"])
    # Retain decision price for opt-in setup-entry gating but exclude it from
    # the model observation sequence.
    if feat_cfg is not None and bool(getattr(feat_cfg, "include_previous_session_pd", False)):
        feat["decision_close"] = primary["close"].reindex(feat.index)
    session = OmegaConf.select(cfg, "session") if cfg is not None else None
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
