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

2. [tutorial example: `cache-identity · code cell 2`](../../../../docs/subjects/A_data_features/examples/cache-identity.ipynb)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
import pandas as pd

from features.pipeline.feature_cache_identity import feature_cache_content_hash

idx = pd.date_range("2026-01-05", periods=3, freq="1min", tz="Etc/GMT-3")
bars = pd.DataFrame(
    {
        "open": [1.0, 2.0, 3.0],
        "high": [2.0, 3.0, 4.0],
        "low": [0.0, 1.0, 2.0],
        "close": [1.5, 2.5, 3.5],
    },
    index=idx,
)
h1 = feature_cache_content_hash(None, bars)
h2 = feature_cache_content_hash(None, bars.copy())
changed = bars.copy()
changed.loc[idx[1], "close"] += 0.25
h3 = feature_cache_content_hash(None, changed)
assert h1 == h2
assert h1 != h3
(h1, h3)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

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

2. [tutorial example: `cache-identity · code cell 2`](../../../../docs/subjects/A_data_features/examples/cache-identity.ipynb)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
import pandas as pd

from features.pipeline.feature_cache_identity import feature_cache_content_hash

idx = pd.date_range("2026-01-05", periods=3, freq="1min", tz="Etc/GMT-3")
bars = pd.DataFrame(
    {
        "open": [1.0, 2.0, 3.0],
        "high": [2.0, 3.0, 4.0],
        "low": [0.0, 1.0, 2.0],
        "close": [1.5, 2.5, 3.5],
    },
    index=idx,
)
h1 = feature_cache_content_hash(None, bars)
h2 = feature_cache_content_hash(None, bars.copy())
changed = bars.copy()
changed.loc[idx[1], "close"] += 0.25
h3 = feature_cache_content_hash(None, changed)
assert h1 == h2
assert h1 != h3
(h1, h3)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

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
