# Features · `pipeline.normalization`

This page contains 3 public callable records owned by `features.pipeline.normalization`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `apply_rolling_zscore_state`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.normalization`

**Purpose:** Apply a serialized train-only fit state without refitting on ``df``.

**Exact API:** {py:obj}`features.pipeline.normalization.apply_rolling_zscore_state` · **Source:** [features/pipeline/normalization.py:106](../../../../features/pipeline/normalization.py#L106)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Feature rows to transform using the saved fit state.
  state: Serialized normalization state captured from training data.
  ```

- **Returns:**

  ```text
  Normalized frame with the same rows and columns as ``df``.
  ```

**Observed usage:**

1. [test fixture: `test_fitted_state_reproduces_frozen_validation_transform`](../../../../tests/unit/features/test_fold_normalize.py#L61)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fitted_state_reproduces_frozen_validation_transform(mode: str) -> None:
    frame = pd.DataFrame({"feature": [10.0, 20.0, 30.0, 40.0, 90.0, 110.0]})
    train_mask = pd.Series([True, True, True, True, False, False])
    state = fit_rolling_zscore_state(frame, train_mask=train_mask, window=2, mode=mode)

    normalized = rolling_zscore(frame, window=2, train_mask=train_mask, mode=mode)
    live = apply_rolling_zscore_state(frame.iloc[4:].copy(), state)

    pd.testing.assert_frame_equal(live, normalized.iloc[4:])
```

2. [test fixture: `test_fitted_state_rejects_changed_feature_order`](../../../../tests/unit/features/test_fold_normalize.py#L75)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fitted_state_rejects_changed_feature_order() -> None:
    frame = pd.DataFrame({"first": [1.0, 2.0], "second": [3.0, 4.0]})
    state = fit_rolling_zscore_state(
        frame,
        train_mask=pd.Series([True, True]),
        window=2,
    )

    with pytest.raises(ValueError, match="columns differ"):
        apply_rolling_zscore_state(frame[["second", "first"]], state)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `fit_rolling_zscore_state`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.normalization`

**Purpose:** Capture the final train-only rolling statistics for inference.

**Exact API:** {py:obj}`features.pipeline.normalization.fit_rolling_zscore_state` · **Source:** [features/pipeline/normalization.py:40](../../../../features/pipeline/normalization.py#L40)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Feature values used to fit the normalization statistics.
  train_mask: Boolean selector identifying training rows.
  window: Number of training observations in each rolling statistic.
  mode: Historical masked-window or frozen-fold fit semantics.
  ```

- **Returns:**

  ```text
  Serializable schema-versioned fit state with final means and scales.
  ```

**Observed usage:**

1. [test fixture: `test_fitted_state_reproduces_frozen_validation_transform`](../../../../tests/unit/features/test_fold_normalize.py#L58)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fitted_state_reproduces_frozen_validation_transform(mode: str) -> None:
    frame = pd.DataFrame({"feature": [10.0, 20.0, 30.0, 40.0, 90.0, 110.0]})
    train_mask = pd.Series([True, True, True, True, False, False])
    state = fit_rolling_zscore_state(frame, train_mask=train_mask, window=2, mode=mode)

    normalized = rolling_zscore(frame, window=2, train_mask=train_mask, mode=mode)
    live = apply_rolling_zscore_state(frame.iloc[4:].copy(), state)

    pd.testing.assert_frame_equal(live, normalized.iloc[4:])
```

2. [test fixture: `test_fitted_state_rejects_changed_feature_order`](../../../../tests/unit/features/test_fold_normalize.py#L68)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fitted_state_rejects_changed_feature_order() -> None:
    frame = pd.DataFrame({"first": [1.0, 2.0], "second": [3.0, 4.0]})
    state = fit_rolling_zscore_state(
        frame,
        train_mask=pd.Series([True, True]),
        window=2,
    )

    with pytest.raises(ValueError, match="columns differ"):
        apply_rolling_zscore_state(frame[["second", "first"]], state)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `rolling_zscore`

**Kind:** function · **Status:** stable · **Owner:** `features.pipeline.normalization`

**Purpose:** Apply a rolling z-score to each column.

**Exact API:** {py:obj}`features.pipeline.normalization.rolling_zscore` · **Source:** [features/pipeline/normalization.py:158](../../../../features/pipeline/normalization.py#L158)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Feature DataFrame.
  window: Look-back window for mean/std (bars).
  train_mask: Boolean Series; if provided, statistics are computed only from rows
      where mask=True (the training fold).  Test rows are normalised using
      the last known training statistics.
  mode: ``legacy_masked_window`` keeps calendar-row rolling statistics on
      training observations and carries the last fitted statistics through
      held-out rows. ``frozen_fold`` computes rolling statistics across
      training observations and forward-fills the final fitted mean/std
      throughout validation, without validation input.
  ```

- **Returns:**

  ```text
  Normalised DataFrame (same shape as input).:
  ```

**Observed usage:**

1. [test fixture: `test_fit_scoped_zscore_ignores_future_poison`](../../../../tests/unit/features/test_feature_cache_and_fit_scope.py#L328)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    idx = pd.date_range("2025-01-01", periods=n, freq="1min", tz="UTC")
    values = np.linspace(0.0, 1.0, n)
    df = pd.DataFrame({"x": values}, index=idx)
    train_mask = pd.Series(np.arange(n) < 100, index=idx)

    clean = rolling_zscore(df, window=20, train_mask=train_mask)
    poisoned = df.copy()
    poisoned.iloc[150:, 0] = 1e6
    scoped = rolling_zscore(poisoned, window=20, train_mask=train_mask)
    pd.testing.assert_series_equal(
        clean.loc[train_mask, "x"],
# … caller assertions omitted …
```

2. [test fixture: `test_frozen_fold_does_not_drift_over_validation_rows`](../../../../tests/unit/features/test_fold_normalize.py#L21)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_frozen_fold_does_not_drift_over_validation_rows() -> None:
    frame = pd.DataFrame({"feature": [10.0, 20.0, 30.0, 40.0, 90.0, 110.0]})
    train_mask = pd.Series([True, True, True, True, False, False])

    normalized = rolling_zscore(frame, window=2, train_mask=train_mask, mode="frozen_fold")

    # Terminal train window = (30, 40), mean=35, population std=5.
    assert normalized.loc[4, "feature"] == pytest.approx((90.0 - 35.0) / 5.0)
    assert normalized.loc[5, "feature"] == pytest.approx((110.0 - 35.0) / 5.0)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
