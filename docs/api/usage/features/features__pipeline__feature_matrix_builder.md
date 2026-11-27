# Features · `pipeline.feature_matrix_builder`

This page contains 2 public callable records owned by `features.pipeline.feature_matrix_builder`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `build_features`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.feature_matrix_builder`

**Purpose:** Build the full feature matrix for the primary instrument.

**Exact API:** {py:obj}`features.pipeline.feature_matrix_builder.build_features` · **Source:** [features/pipeline/feature_matrix_builder.py:155](../../../../features/pipeline/feature_matrix_builder.py#L155)

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

1. [test fixture: `test_missing_cached_d1_fit_rebuilds_source_normalization_state`](../../../../tests/unit/features/test_feature_matrix_builder_remaining_contracts.py#L78)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    cfg.features.zscore_window = 3
    train_mask = pd.Series(np.arange(len(primary)) < 160, index=primary.index)
    cache_path = tmp_path / "features.parquet"
    fit_state_path = tmp_path / "normalization.json"

    original = build_features(
        primary,
        cfg=cfg,
        train_mask=train_mask,
        timeframe_bars={"D1": daily},
        cache_path=cache_path,
        fit_state_path=fit_state_path,
        force=True,
    )
    damaged_state: dict[str, Any] = json.loads(fit_state_path.read_text(encoding="utf-8"))
    assert "source:D1" in damaged_state["stages"]
    del damaged_state["stages"]["source:D1"]
    fit_state_path.write_text(json.dumps(damaged_state), encoding="utf-8")

# … caller assertions omitted …
```

2. [test fixture: `test_empty_secondary_timeframe_keeps_m1_smt_and_skips_only_that_htf_block`](../../../../tests/unit/features/test_feature_matrix_builder_remaining_contracts.py#L133)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    cfg.features.structure.enabled = False
    cfg.features.smt.enabled = True
    cfg.features.smt.timeframes = ["M1", "M5"]
    cfg.features.zscore_window = 10

    features = build_features(
        primary,
        secondary=secondary,
        cfg=cfg,
        secondary_timeframe_bars={"M5": empty_m5},
        force=True,
    )

    assert "smt_corr" in features
    assert "M5_smt_corr" not in features
    assert not any(str(column).startswith("M1_") for column in features.columns)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `build_features`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.feature_matrix_builder`

**Purpose:** Build the full feature matrix for the primary instrument.

**Exact API:** {py:obj}`features.pipeline.feature_matrix_builder.build_features` · **Source:** [features/pipeline/feature_matrix_builder.py:155](../../../../features/pipeline/feature_matrix_builder.py#L155)

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

1. [test fixture: `test_missing_cached_d1_fit_rebuilds_source_normalization_state`](../../../../tests/unit/features/test_feature_matrix_builder_remaining_contracts.py#L78)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    cfg.features.zscore_window = 3
    train_mask = pd.Series(np.arange(len(primary)) < 160, index=primary.index)
    cache_path = tmp_path / "features.parquet"
    fit_state_path = tmp_path / "normalization.json"

    original = build_features(
        primary,
        cfg=cfg,
        train_mask=train_mask,
        timeframe_bars={"D1": daily},
        cache_path=cache_path,
        fit_state_path=fit_state_path,
        force=True,
    )
    damaged_state: dict[str, Any] = json.loads(fit_state_path.read_text(encoding="utf-8"))
    assert "source:D1" in damaged_state["stages"]
    del damaged_state["stages"]["source:D1"]
    fit_state_path.write_text(json.dumps(damaged_state), encoding="utf-8")

# … caller assertions omitted …
```

2. [test fixture: `test_empty_secondary_timeframe_keeps_m1_smt_and_skips_only_that_htf_block`](../../../../tests/unit/features/test_feature_matrix_builder_remaining_contracts.py#L133)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    cfg.features.structure.enabled = False
    cfg.features.smt.enabled = True
    cfg.features.smt.timeframes = ["M1", "M5"]
    cfg.features.zscore_window = 10

    features = build_features(
        primary,
        secondary=secondary,
        cfg=cfg,
        secondary_timeframe_bars={"M5": empty_m5},
        force=True,
    )

    assert "smt_corr" in features
    assert "M5_smt_corr" not in features
    assert not any(str(column).startswith("M1_") for column in features.columns)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
