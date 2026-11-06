# Features · `pipeline.feature_matrix_builder`

This page contains 2 public callable records owned by `features.pipeline.feature_matrix_builder`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_features`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.feature_matrix_builder`

**Purpose:** Build the full feature matrix for the primary instrument.

**Exact API:** {py:obj}`features.pipeline.feature_matrix_builder.build_features` · **Source:** [features/pipeline/feature_matrix_builder.py:153](../../../../features/pipeline/feature_matrix_builder.py#L153)

**Inputs and outputs:**

- **Args:**

  ```text
  primary: Cleaned, session-filtered M1 DataFrame (US100).
  secondary: US500 M1 DataFrame for SMT divergence (optional but recommended).
  cfg: Full OmegaConf config; ``cfg.features`` sub-node is used.
  train_mask: Boolean Series aligned to primary index; True = training bar.
  cache_path: If given, save/load feature parquet here.
  force: Ignore existing cache.
  normalization_mode: Normalization behavior used for continuous feature columns.
  timeframe_bars: Optional precomputed primary bars indexed by timeframe.
  secondary_timeframe_bars: Optional precomputed correlated-symbol bars by timeframe.
  fit_state_path: Persist the train-only normalization fit state beside this run/cache.
  fitted_normalization_state: Apply a previously captured state without refitting.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``build_features``.
  ```

**Observed usage:**

1. [production caller: `_build_chart_features`](../../../../evaluation/reporting/order_chart_regeneration.py#L98)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _build_chart_features(
    run_cfg: Any,
    feature_cfg: Any,
    primary: pd.DataFrame,
    secondary: pd.DataFrame | None,
) -> pd.DataFrame:
    train_mask = _chart_feature_train_mask(run_cfg, pd.DatetimeIndex(primary.index))
    return build_features(
        primary,
        secondary=secondary,
        cfg=feature_cfg,
        train_mask=train_mask,
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `build_features`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.feature_matrix_builder`

**Purpose:** Build the full feature matrix for the primary instrument.

**Exact API:** {py:obj}`features.pipeline.feature_matrix_builder.build_features` · **Source:** [features/pipeline/feature_matrix_builder.py:153](../../../../features/pipeline/feature_matrix_builder.py#L153)

**Inputs and outputs:**

- **Args:**

  ```text
  primary: Cleaned, session-filtered M1 DataFrame (US100).
  secondary: US500 M1 DataFrame for SMT divergence (optional but recommended).
  cfg: Full OmegaConf config; ``cfg.features`` sub-node is used.
  train_mask: Boolean Series aligned to primary index; True = training bar.
  cache_path: If given, save/load feature parquet here.
  force: Ignore existing cache.
  normalization_mode: Normalization behavior used for continuous feature columns.
  timeframe_bars: Optional precomputed primary bars indexed by timeframe.
  secondary_timeframe_bars: Optional precomputed correlated-symbol bars by timeframe.
  fit_state_path: Persist the train-only normalization fit state beside this run/cache.
  fitted_normalization_state: Apply a previously captured state without refitting.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``build_features``.
  ```

**Observed usage:**

1. [production caller: `_build_chart_features`](../../../../evaluation/reporting/order_chart_regeneration.py#L98)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _build_chart_features(
    run_cfg: Any,
    feature_cfg: Any,
    primary: pd.DataFrame,
    secondary: pd.DataFrame | None,
) -> pd.DataFrame:
    train_mask = _chart_feature_train_mask(run_cfg, pd.DatetimeIndex(primary.index))
    return build_features(
        primary,
        secondary=secondary,
        cfg=feature_cfg,
        train_mask=train_mask,
    )
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
