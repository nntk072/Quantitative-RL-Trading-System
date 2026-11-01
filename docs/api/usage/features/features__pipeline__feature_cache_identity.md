# Features · `pipeline.feature_cache_identity`

This page contains 4 public callable records owned by `features.pipeline.feature_cache_identity`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `feature_cache_content_hash`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.feature_cache_identity`

**Purpose:** Stable short hash for feature-cache invalidation (TI-3).

**Exact API:** {py:obj}`features.pipeline.feature_cache_identity.feature_cache_content_hash` · **Source:** [features/pipeline/feature_cache_identity.py:20](../../../../features/pipeline/feature_cache_identity.py#L20)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  primary: Tabular data used for the primary.
  train_mask: Boolean mask identifying rows available for fitting.
  secondary: Tabular data used for the secondary.
  normalization_mode: Text or path value identifying the normalization mode.
  timeframe_bars: Market bar or price data used for stable short hash for feature-cache invalidation (TI-3).
  secondary_timeframe_bars: Market bar or price data used for stable short hash for feature-cache invalidation (TI-3).
  ```

- **Returns:**

  ```text
  Text returned by ``feature_cache_content_hash``.
  ```

**Observed usage:**

1. [production caller: `feature_cache_path`](../../../../features/pipeline/feature_cache_identity.py#L178)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def feature_cache_path(
    cache_dir: Path | str,
    symbol: str,
    cfg: DictConfig | None,
    primary: pd.DataFrame,
    train_mask: pd.Series | None = None,
    secondary: pd.DataFrame | None = None,
    normalization_mode: str = "legacy_masked_window",
    timeframe_bars: dict[str, pd.DataFrame] | None = None,
    secondary_timeframe_bars: dict[str, pd.DataFrame] | None = None,
) -> Path:
    digest = feature_cache_content_hash(
        cfg,
        primary,
        train_mask=train_mask,
        secondary=secondary,
        normalization_mode=normalization_mode,
        timeframe_bars=timeframe_bars,
        secondary_timeframe_bars=secondary_timeframe_bars,
    )
    return Path(cache_dir) / f"{symbol}_features_{FEATURE_CACHE_VERSION}_{digest}.parquet"
```

2. [production caller: `build_features`](../../../../features/pipeline/feature_matrix_builder.py#L107)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    expected_hash = feature_cache_content_hash(
        cfg,
        primary,
        train_mask=train_mask,
        secondary=secondary,
        normalization_mode=normalization_mode,
        timeframe_bars=timeframe_bars,
        secondary_timeframe_bars=secondary_timeframe_bars,
    )
    requested_reference_mode = str(
        (OmegaConf.select(cfg, "features.po3_reference_mode") if cfg is not None else None)
        or "m1_legacy"
    )
    sweep_audit_path = Path(str(cache_path) + ".htf_sweeps.parquet") if cache_path else None
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `feature_cache_path`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.feature_cache_identity`

**Purpose:** Build ``{symbol}_features_{version}_{hash}.parquet`` under ``cache_dir``.

**Exact API:** {py:obj}`features.pipeline.feature_cache_identity.feature_cache_path` · **Source:** [features/pipeline/feature_cache_identity.py:151](../../../../features/pipeline/feature_cache_identity.py#L151)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_dir: Directory used to store or read cached data.
  symbol: Text or path value identifying the symbol.
  cfg: Run configuration used by this operation.
  primary: Tabular data used for the primary.
  train_mask: Boolean mask identifying rows available for fitting.
  secondary: Tabular data used for the secondary.
  normalization_mode: Text or path value identifying the normalization mode.
  timeframe_bars: Market bar or price data used for build ``{symbol}_features_{version}_{hash}.parquet`` under ``cache_dir``.
  secondary_timeframe_bars: Market bar or price data used for build ``{symbol}_features_{version}_{hash}.parquet`` under ``cache_dir``.
  ```

- **Returns:**

  ```text
  Path returned by ``feature_cache_path``.
  ```

**Observed usage:**

1. [production caller: `build_walkforward_fold_features`](../../../../features/pipeline/walkforward_feature_fitting.py#L62)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    last_validation_bar = validation_index.max()
    context_primary = primary.loc[:last_validation_bar]
    context_secondary = secondary.loc[:last_validation_bar] if secondary is not None else None
    fold_mask = pd.Series(context_primary.index.isin(train_index), index=context_primary.index)
    cache = feature_cache_path(
        cache_dir,
        symbol,
        cfg,
        context_primary,
        train_mask=fold_mask,
        secondary=context_secondary,
        normalization_mode="frozen_fold",
    )
    from features import build_features

    features = build_features(
        context_primary,
        secondary=context_secondary,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `feature_cache_content_hash`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.feature_cache_identity`

**Purpose:** Stable short hash for feature-cache invalidation (TI-3).

**Exact API:** {py:obj}`features.pipeline.feature_cache_identity.feature_cache_content_hash` · **Source:** [features/pipeline/feature_cache_identity.py:20](../../../../features/pipeline/feature_cache_identity.py#L20)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  primary: Tabular data used for the primary.
  train_mask: Boolean mask identifying rows available for fitting.
  secondary: Tabular data used for the secondary.
  normalization_mode: Text or path value identifying the normalization mode.
  timeframe_bars: Market bar or price data used for stable short hash for feature-cache invalidation (TI-3).
  secondary_timeframe_bars: Market bar or price data used for stable short hash for feature-cache invalidation (TI-3).
  ```

- **Returns:**

  ```text
  Text returned by ``feature_cache_content_hash``.
  ```

**Observed usage:**

1. [production caller: `feature_cache_path`](../../../../features/pipeline/feature_cache_identity.py#L178)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def feature_cache_path(
    cache_dir: Path | str,
    symbol: str,
    cfg: DictConfig | None,
    primary: pd.DataFrame,
    train_mask: pd.Series | None = None,
    secondary: pd.DataFrame | None = None,
    normalization_mode: str = "legacy_masked_window",
    timeframe_bars: dict[str, pd.DataFrame] | None = None,
    secondary_timeframe_bars: dict[str, pd.DataFrame] | None = None,
) -> Path:
    digest = feature_cache_content_hash(
        cfg,
        primary,
        train_mask=train_mask,
        secondary=secondary,
        normalization_mode=normalization_mode,
        timeframe_bars=timeframe_bars,
        secondary_timeframe_bars=secondary_timeframe_bars,
    )
    return Path(cache_dir) / f"{symbol}_features_{FEATURE_CACHE_VERSION}_{digest}.parquet"
```

2. [production caller: `build_features`](../../../../features/pipeline/feature_matrix_builder.py#L107)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    expected_hash = feature_cache_content_hash(
        cfg,
        primary,
        train_mask=train_mask,
        secondary=secondary,
        normalization_mode=normalization_mode,
        timeframe_bars=timeframe_bars,
        secondary_timeframe_bars=secondary_timeframe_bars,
    )
    requested_reference_mode = str(
        (OmegaConf.select(cfg, "features.po3_reference_mode") if cfg is not None else None)
        or "m1_legacy"
    )
    sweep_audit_path = Path(str(cache_path) + ".htf_sweeps.parquet") if cache_path else None
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `feature_cache_path`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.feature_cache_identity`

**Purpose:** Build ``{symbol}_features_{version}_{hash}.parquet`` under ``cache_dir``.

**Exact API:** {py:obj}`features.pipeline.feature_cache_identity.feature_cache_path` · **Source:** [features/pipeline/feature_cache_identity.py:151](../../../../features/pipeline/feature_cache_identity.py#L151)

**Inputs and outputs:**

- **Args:**

  ```text
  cache_dir: Directory used to store or read cached data.
  symbol: Text or path value identifying the symbol.
  cfg: Run configuration used by this operation.
  primary: Tabular data used for the primary.
  train_mask: Boolean mask identifying rows available for fitting.
  secondary: Tabular data used for the secondary.
  normalization_mode: Text or path value identifying the normalization mode.
  timeframe_bars: Market bar or price data used for build ``{symbol}_features_{version}_{hash}.parquet`` under ``cache_dir``.
  secondary_timeframe_bars: Market bar or price data used for build ``{symbol}_features_{version}_{hash}.parquet`` under ``cache_dir``.
  ```

- **Returns:**

  ```text
  Path returned by ``feature_cache_path``.
  ```

**Observed usage:**

1. [production caller: `build_walkforward_fold_features`](../../../../features/pipeline/walkforward_feature_fitting.py#L62)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …

    last_validation_bar = validation_index.max()
    context_primary = primary.loc[:last_validation_bar]
    context_secondary = secondary.loc[:last_validation_bar] if secondary is not None else None
    fold_mask = pd.Series(context_primary.index.isin(train_index), index=context_primary.index)
    cache = feature_cache_path(
        cache_dir,
        symbol,
        cfg,
        context_primary,
        train_mask=fold_mask,
        secondary=context_secondary,
        normalization_mode="frozen_fold",
    )
    from features import build_features

    features = build_features(
        context_primary,
        secondary=context_secondary,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
