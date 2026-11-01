# Features · `pipeline.walkforward_feature_fitting`

This page contains 2 public callable records owned by `features.pipeline.walkforward_feature_fitting`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_walkforward_fold_features`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.walkforward_feature_fitting`

**Purpose:** Refit normalization on one fold with causal warm-up bars.

**Exact API:** {py:obj}`features.pipeline.walkforward_feature_fitting.build_walkforward_fold_features` · **Source:** [features/pipeline/walkforward_feature_fitting.py:13](../../../../features/pipeline/walkforward_feature_fitting.py#L13)

**Inputs and outputs:**

- **Args:**

  ```text
  primary: Tabular data used for the primary.
  secondary: Tabular data used for the secondary.
  cfg: Run configuration used by this operation.
  fold_train_bars: Market bar or price data used for refit normalization on one fold with causal warm-up bars.
  fold_validation_bars: Market bar or price data used for refit normalization on one fold with causal warm-up bars.
  cache_dir: Directory used to store or read cached data.
  symbol: Text or path value identifying the symbol.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``build_walkforward_fold_features``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = build_walkforward_fold_features(primary=..., secondary=..., cfg=..., fold_train_bars=..., fold_validation_bars=..., cache_dir=..., symbol=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `build_walkforward_fold_features`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.walkforward_feature_fitting`

**Purpose:** Refit normalization on one fold with causal warm-up bars.

**Exact API:** {py:obj}`features.pipeline.walkforward_feature_fitting.build_walkforward_fold_features` · **Source:** [features/pipeline/walkforward_feature_fitting.py:13](../../../../features/pipeline/walkforward_feature_fitting.py#L13)

**Inputs and outputs:**

- **Args:**

  ```text
  primary: Tabular data used for the primary.
  secondary: Tabular data used for the secondary.
  cfg: Run configuration used by this operation.
  fold_train_bars: Market bar or price data used for refit normalization on one fold with causal warm-up bars.
  fold_validation_bars: Market bar or price data used for refit normalization on one fold with causal warm-up bars.
  cache_dir: Directory used to store or read cached data.
  symbol: Text or path value identifying the symbol.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``build_walkforward_fold_features``.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = build_walkforward_fold_features(primary=..., secondary=..., cfg=..., fold_train_bars=..., fold_validation_bars=..., cache_dir=..., symbol=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
