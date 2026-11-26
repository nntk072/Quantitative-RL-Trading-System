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

1. [test fixture: `test_pipeline_development_cutoff_excludes_later_bar_values`](../../../../tests/integration/test_pipeline_splits.py#L362)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert frames[symbol]["M1"]["close"].tolist() == [100.0, 101.0]
    assert frames[symbol]["M1"].index[-1] == pd.Timestamp("2025-12-31 23:59:59+03:00")
    assert not any(value >= 900_001.0 for value in frames[symbol]["M1"]["close"])
    assert not (tmp_path / "cache").exists()

    first_key = feature_cache_content_hash(None, frames[symbol]["M1"])
    testing_path = tmp_path / "testing" / names[symbol]
    testing_path.write_text(
        testing_path.read_text(encoding="utf-8").replace("900001.0", "900999.0"),
        encoding="utf-8",
    )
# … caller assertions omitted …
```

2. [test fixture: `test_feature_cache_key_changes_when_an_undeclared_build_source_changes`](../../../../tests/unit/features/test_feature_source_identity.py#L122)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_feature_cache_key_changes_when_an_undeclared_build_source_changes(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(registry, "SOURCE_ROOTS", _seeds(project))
    monkeypatch.setattr(registry, "_REPO_ROOT", project)
    frame = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0]},
        index=pd.DatetimeIndex(["2025-01-06 00:00"], tz="UTC"),
    )
    before = feature_cache_content_hash(None, frame)
    assert feature_cache_content_hash(None, frame) == before
    (project / "helper_pkg" / "inner.py").write_text("VALUE = 3\n", encoding="utf-8")
    assert feature_cache_content_hash(None, frame) != before
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `feature_cache_path`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.feature_cache_identity`

**Purpose:** Build ``{symbol}_features_{version}_{hash}.parquet`` under ``cache_dir``.

**Exact API:** {py:obj}`features.pipeline.feature_cache_identity.feature_cache_path` · **Source:** [features/pipeline/feature_cache_identity.py:158](../../../../features/pipeline/feature_cache_identity.py#L158)

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

1. [test fixture: `test_pipeline_development_cutoff_excludes_later_bar_values`](../../../../tests/integration/test_pipeline_splits.py#L362)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert frames[symbol]["M1"]["close"].tolist() == [100.0, 101.0]
    assert frames[symbol]["M1"].index[-1] == pd.Timestamp("2025-12-31 23:59:59+03:00")
    assert not any(value >= 900_001.0 for value in frames[symbol]["M1"]["close"])
    assert not (tmp_path / "cache").exists()

    first_key = feature_cache_content_hash(None, frames[symbol]["M1"])
    testing_path = tmp_path / "testing" / names[symbol]
    testing_path.write_text(
        testing_path.read_text(encoding="utf-8").replace("900001.0", "900999.0"),
        encoding="utf-8",
    )
# … caller assertions omitted …
```

2. [test fixture: `test_feature_cache_key_changes_when_an_undeclared_build_source_changes`](../../../../tests/unit/features/test_feature_source_identity.py#L122)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_feature_cache_key_changes_when_an_undeclared_build_source_changes(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(registry, "SOURCE_ROOTS", _seeds(project))
    monkeypatch.setattr(registry, "_REPO_ROOT", project)
    frame = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0]},
        index=pd.DatetimeIndex(["2025-01-06 00:00"], tz="UTC"),
    )
    before = feature_cache_content_hash(None, frame)
    assert feature_cache_content_hash(None, frame) == before
    (project / "helper_pkg" / "inner.py").write_text("VALUE = 3\n", encoding="utf-8")
    assert feature_cache_content_hash(None, frame) != before
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `feature_cache_path`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.feature_cache_identity`

**Purpose:** Build ``{symbol}_features_{version}_{hash}.parquet`` under ``cache_dir``.

**Exact API:** {py:obj}`features.pipeline.feature_cache_identity.feature_cache_path` · **Source:** [features/pipeline/feature_cache_identity.py:158](../../../../features/pipeline/feature_cache_identity.py#L158)

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
