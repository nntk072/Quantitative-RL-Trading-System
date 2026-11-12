# Market data · `splits.definitions`

This page contains 8 public callable records owned by `market_data.splits.definitions`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `get_split_config`

**Kind:** function · **Status:** stable · **Owner:** `market_data.splits.definitions`

**Purpose:** Extract *train_end* / *test_start* from config with fallback defaults.

**Exact API:** {py:obj}`market_data.splits.definitions.get_split_config` · **Source:** [market_data/splits/definitions.py:117](../../../../market_data/splits/definitions.py#L117)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Values returned by ``get_split_config``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_get_split_config_fallback`](../../../../tests/unit/market_data/test_data_split.py#L88)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_get_split_config_fallback():
    train_end, test_start = get_split_config(None)
    assert train_end == "2025-12-31"
    assert test_start == "2026-01-01"
```

2. [production caller: `reconstruct_reanalysis_datasets`](../../../../evaluation/reanalysis/datasets.py#L134)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        symbols=[primary_symbol],
        datasets=selected_datasets,
    ).get(primary_symbol)

    cache_dir = Path(cfg.data.cache_dir)
    train_end, test_start = get_split_config(cfg)
    train_start = get_train_start_config(cfg)
    source_cache_replay_path: Path | None = None
    train_feature_snapshot_path: Path | None = None
    if args.train_only_feature_snapshot:
        features, train_feature_snapshot_path, evaluated_feature_cache_file_sha256 = (
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `make_train_mask`

**Kind:** function · **Status:** stable · **Owner:** `market_data.splits.definitions`

**Purpose:** Boolean mask for the inclusive configured training date range.

**Exact API:** {py:obj}`market_data.splits.definitions.make_train_mask` · **Source:** [market_data/splits/definitions.py:153](../../../../market_data/splits/definitions.py#L153)

**Inputs and outputs:**

- **Args:**

  ```text
  index: Position or label identifying the requested item.
  train_end: Text or path value identifying the train end.
  train_start: Train start used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of boolean mask for the inclusive configured training date range.
  ```

**Observed usage:**

1. [test fixture: `test_inclusive_train_end_keeps_subsecond_rows_and_excludes_next_midnight`](../../../../tests/unit/market_data/test_data_split.py#L131)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        ]
    )
    bars = pd.DataFrame({"close": [1.0, 2.0]}, index=index)

    train, test, _, _ = split_train_test(bars, bars, "2025-12-31", "2026-01-01")
    mask = make_train_mask(index, "2025-12-31")

    assert train.index.equals(index[:1])
    assert test.index.equals(index[1:])
    assert mask.tolist() == [True, False]
```

2. [test fixture: `test_inclusive_train_end_uses_local_calendar_day_across_dst`](../../../../tests/unit/market_data/test_data_split.py#L148)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        ]
    ).tz_convert("America/New_York")
    bars = pd.DataFrame({"close": [1.0, 2.0]}, index=index)

    train, test, _, _ = split_train_test(bars, bars, "2025-03-08", "2025-03-09")
    mask = make_train_mask(index, "2025-03-08")

    assert train.index.equals(index[:1])
    assert test.index.equals(index[1:])
    assert mask.tolist() == [True, False]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `split_train_test`

**Kind:** function · **Status:** stable · **Owner:** `market_data.splits.definitions`

**Purpose:** Split aligned bars + features into train (≤ *train_end*) and test (≥ *test_start*).

**Exact API:** {py:obj}`market_data.splits.definitions.split_train_test` · **Source:** [market_data/splits/definitions.py:16](../../../../market_data/splits/definitions.py#L16)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars indexed by timestamp.
  features: Feature rows aligned to the market bars' index.
  train_end: Last date included in the training set (inclusive, full day).
  test_start: First date included in the test set (inclusive, midnight).
  train_start: Optional first date exposed to the training environment. Earlier rows
      remain available for causal feature warmup but are not training rows.
  ```

- **Returns:**

  ```text
  Tuple of ``train_bars``, ``test_bars``, ``train_features``, and
  ``test_features`` in that order.
  ```

**Observed usage:**

1. [test fixture: `test_smoke_fixture_spans_default_split`](../../../../tests/integration/test_scripts_smoke.py#L237)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_smoke_fixture_spans_default_split(tmp_path: Path) -> None:
    from market_data.splits.definitions import split_train_test

    bars = pd.read_csv(_make_bars_csv(tmp_path / "bars.csv"), index_col=0, parse_dates=True)
    features = bars.select_dtypes(include=["number"])
    train_bars, test_bars, _, _ = split_train_test(bars, features)
    assert not train_bars.empty
    assert not test_bars.empty
```

2. [test fixture: `test_train_max_date`](../../../../tests/unit/market_data/test_data_split.py#L36)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_train_max_date(self):
    tr_b, _, _, _ = split_train_test(self.bars, self.feat, "2025-12-31", "2026-01-01")
    assert tr_b.index.max() <= pd.Timestamp("2025-12-31", tz="Etc/GMT-3") + pd.Timedelta(days=1)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `get_split_config`

**Kind:** function · **Status:** stable · **Owner:** `market_data.splits.definitions`

**Purpose:** Extract *train_end* / *test_start* from config with fallback defaults.

**Exact API:** {py:obj}`market_data.splits.definitions.get_split_config` · **Source:** [market_data/splits/definitions.py:117](../../../../market_data/splits/definitions.py#L117)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Values returned by ``get_split_config``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_get_split_config_fallback`](../../../../tests/unit/market_data/test_data_split.py#L88)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_get_split_config_fallback():
    train_end, test_start = get_split_config(None)
    assert train_end == "2025-12-31"
    assert test_start == "2026-01-01"
```

2. [production caller: `reconstruct_reanalysis_datasets`](../../../../evaluation/reanalysis/datasets.py#L134)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        symbols=[primary_symbol],
        datasets=selected_datasets,
    ).get(primary_symbol)

    cache_dir = Path(cfg.data.cache_dir)
    train_end, test_start = get_split_config(cfg)
    train_start = get_train_start_config(cfg)
    source_cache_replay_path: Path | None = None
    train_feature_snapshot_path: Path | None = None
    if args.train_only_feature_snapshot:
        features, train_feature_snapshot_path, evaluated_feature_cache_file_sha256 = (
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `get_train_start_config`

**Kind:** function · **Status:** stable · **Owner:** `market_data.splits.definitions`

**Purpose:** Read the optional first train date without changing legacy split config.

**Exact API:** {py:obj}`market_data.splits.definitions.get_train_start_config` · **Source:** [market_data/splits/definitions.py:137](../../../../market_data/splits/definitions.py#L137)

**Inputs and outputs:**

- **Args:**

  ```text
  cfg: Run configuration used by this operation.
  ```

- **Returns:**

  ```text
  Result of read the optional first train date without changing legacy split config.
  ```

**Observed usage:**

1. [production caller: `reconstruct_reanalysis_datasets`](../../../../evaluation/reanalysis/datasets.py#L135)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        datasets=selected_datasets,
    ).get(primary_symbol)

    cache_dir = Path(cfg.data.cache_dir)
    train_end, test_start = get_split_config(cfg)
    train_start = get_train_start_config(cfg)
    source_cache_replay_path: Path | None = None
    train_feature_snapshot_path: Path | None = None
    if args.train_only_feature_snapshot:
        features, train_feature_snapshot_path, evaluated_feature_cache_file_sha256 = (
            _load_train_only_feature_snapshot(
# … caller assertions omitted …
```

2. [production caller: `_chart_feature_train_mask`](../../../../evaluation/reporting/order_chart_regeneration.py#L77)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _chart_feature_train_mask(cfg: Any, index: pd.DatetimeIndex) -> pd.Series:
    train_end, _ = get_split_config(cfg)
    return make_train_mask(index, train_end, get_train_start_config(cfg))
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `make_train_mask`

**Kind:** function · **Status:** stable · **Owner:** `market_data.splits.definitions`

**Purpose:** Boolean mask for the inclusive configured training date range.

**Exact API:** {py:obj}`market_data.splits.definitions.make_train_mask` · **Source:** [market_data/splits/definitions.py:153](../../../../market_data/splits/definitions.py#L153)

**Inputs and outputs:**

- **Args:**

  ```text
  index: Position or label identifying the requested item.
  train_end: Text or path value identifying the train end.
  train_start: Train start used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of boolean mask for the inclusive configured training date range.
  ```

**Observed usage:**

1. [test fixture: `test_inclusive_train_end_keeps_subsecond_rows_and_excludes_next_midnight`](../../../../tests/unit/market_data/test_data_split.py#L131)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        ]
    )
    bars = pd.DataFrame({"close": [1.0, 2.0]}, index=index)

    train, test, _, _ = split_train_test(bars, bars, "2025-12-31", "2026-01-01")
    mask = make_train_mask(index, "2025-12-31")

    assert train.index.equals(index[:1])
    assert test.index.equals(index[1:])
    assert mask.tolist() == [True, False]
```

2. [test fixture: `test_inclusive_train_end_uses_local_calendar_day_across_dst`](../../../../tests/unit/market_data/test_data_split.py#L148)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        ]
    ).tz_convert("America/New_York")
    bars = pd.DataFrame({"close": [1.0, 2.0]}, index=index)

    train, test, _, _ = split_train_test(bars, bars, "2025-03-08", "2025-03-09")
    mask = make_train_mask(index, "2025-03-08")

    assert train.index.equals(index[:1])
    assert test.index.equals(index[1:])
    assert mask.tolist() == [True, False]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `split_bars`

**Kind:** function · **Status:** stable · **Owner:** `market_data.splits.definitions`

**Purpose:** Split a single bar frame on the same date boundaries as ``split_train_test``.

**Exact API:** {py:obj}`market_data.splits.definitions.split_bars` · **Source:** [market_data/splits/definitions.py:77](../../../../market_data/splits/definitions.py#L77)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  train_end: Text or path value identifying the train end.
  test_start: Text or path value identifying the test start.
  train_start: Train start used by the operation described above.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``split_bars``.
  ```

**Observed usage:**

1. [test fixture: `test_split_bars_matches_split_train_test`](../../../../tests/unit/market_data/test_data_split.py#L115)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_split_bars_matches_split_train_test() -> None:
    bars = pd.concat(
        [
            _make_bars("2025-12-30", "2025-12-31"),
            _make_bars("2026-01-01", "2026-01-02"),
        ]
    )
    tr, te = split_bars(bars, "2025-12-31", "2026-01-01")
    tr_b, te_b, _, _ = split_train_test(bars, bars, "2025-12-31", "2026-01-01")
    assert tr.index.equals(tr_b.index)
    assert te.index.equals(te_b.index)
```

2. [production caller: `reconstruct_reanalysis_datasets`](../../../../evaluation/reanalysis/datasets.py#L231)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    train_bars, test_bars, train_features, test_features = split_train_test(
        primary_m1, features, train_end, test_start, train_start
    )
    train_secondary = test_secondary = None
    if secondary_m1 is not None and not secondary_m1.empty:
        train_secondary, test_secondary = split_bars(
            secondary_m1, train_end, test_start, train_start
        )
    evaluated_datasets = _evaluation_dataset_records(
        train_bars=train_bars,
        train_features=train_features,
        test_bars=test_bars,
        test_features=test_features,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `split_train_test`

**Kind:** function · **Status:** stable · **Owner:** `market_data.splits.definitions`

**Purpose:** Split aligned bars + features into train (≤ *train_end*) and test (≥ *test_start*).

**Exact API:** {py:obj}`market_data.splits.definitions.split_train_test` · **Source:** [market_data/splits/definitions.py:16](../../../../market_data/splits/definitions.py#L16)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars indexed by timestamp.
  features: Feature rows aligned to the market bars' index.
  train_end: Last date included in the training set (inclusive, full day).
  test_start: First date included in the test set (inclusive, midnight).
  train_start: Optional first date exposed to the training environment. Earlier rows
      remain available for causal feature warmup but are not training rows.
  ```

- **Returns:**

  ```text
  Tuple of ``train_bars``, ``test_bars``, ``train_features``, and
  ``test_features`` in that order.
  ```

**Observed usage:**

1. [test fixture: `test_smoke_fixture_spans_default_split`](../../../../tests/integration/test_scripts_smoke.py#L237)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_smoke_fixture_spans_default_split(tmp_path: Path) -> None:
    from market_data.splits.definitions import split_train_test

    bars = pd.read_csv(_make_bars_csv(tmp_path / "bars.csv"), index_col=0, parse_dates=True)
    features = bars.select_dtypes(include=["number"])
    train_bars, test_bars, _, _ = split_train_test(bars, features)
    assert not train_bars.empty
    assert not test_bars.empty
```

2. [test fixture: `test_train_max_date`](../../../../tests/unit/market_data/test_data_split.py#L36)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_train_max_date(self):
    tr_b, _, _, _ = split_train_test(self.bars, self.feat, "2025-12-31", "2026-01-01")
    assert tr_b.index.max() <= pd.Timestamp("2025-12-31", tz="Etc/GMT-3") + pd.Timedelta(days=1)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
