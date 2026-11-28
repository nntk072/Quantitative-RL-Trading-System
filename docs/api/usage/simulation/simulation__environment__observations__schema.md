# Simulation · `environment.observations.schema`

This page contains 8 public callable records owned by `simulation.environment.observations.schema`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `closed_window`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.observations.schema`

**Purpose:** Last ``length`` closed runs at or before ``end``, oldest to newest.

**Exact API:** {py:obj}`simulation.environment.observations.schema.closed_window` · **Source:** [simulation/environment/observations/schema.py:516](../../../../simulation/environment/observations/schema.py#L516)

**Inputs and outputs:**

- **Args:**

  ```text
  block: Block used by the operation described above.
  starts: Starts used by the operation described above.
  end: Numeric value used for the end.
  length: Numeric value used for the length.
  columns: Columns used by the operation described above.
  include_validity: Append per-feature finite-value mask channels.
  ```

- **Returns:**

  ```text
  Array returned by ``closed_window``.
  ```

**Observed usage:**

1. [test fixture: `test_closed_m5_window_ends_on_the_candle_that_closed_at_1035`](../../../../tests/unit/simulation/test_environment/test_mtf_windows.py#L30)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_closed_m5_window_ends_on_the_candle_that_closed_at_1035() -> None:
    index = pd.date_range("2020-01-02 09:00", "2020-01-02 11:00", freq="1min")
    minute = index.hour * 60 + index.minute
    block = ((minute // 5) * 5).to_numpy(dtype=np.float64).reshape(-1, 1)
    decision = int(index.searchsorted(pd.Timestamp("2020-01-02 10:37")))
    window, mask = closed_window(block, run_starts(block), decision, 24)
    newest = window[mask > 0][-3:, 0]
    np.testing.assert_array_equal(newest, [10 * 60 + 25, 10 * 60 + 30, 10 * 60 + 35])
    assert not np.any(window == 10 * 60 + 40)
```

2. [test fixture: `test_closed_window_column_selection_matches_materialized_branch`](../../../../tests/unit/simulation/test_environment/test_mtf_windows.py#L44)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_closed_window_column_selection_matches_materialized_branch() -> None:
    block = np.arange(120, dtype=np.float32).reshape(30, 4)
    block[8, 3] = np.nan
    starts = np.asarray([0, 3, 6, 9, 12, 15, 18, 21, 24, 27], dtype=np.int64)
    columns = np.asarray([1, 3], dtype=np.int64)

    for decision, length in ((0, 4), (5, 4), (18, 3), (29, 4)):
        expected, expected_mask = closed_window(block[:, columns], starts, decision, length)
        actual, actual_mask = closed_window(block, starts, decision, length, columns=columns)
        np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(actual_mask, expected_mask)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `closed_window_raw`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.observations.schema`

**Purpose:** Raw float32 rows of ``closed_window`` before sanitizing and padding.

**Exact API:** {py:obj}`simulation.environment.observations.schema.closed_window_raw` · **Source:** [simulation/environment/observations/schema.py:172](../../../../simulation/environment/observations/schema.py#L172)

**Inputs and outputs:**

- **Args:**

  ```text
  block: Feature block to gather from.
  starts: Starts of each closed run.
  end: Decision row.
  length: Window length in runs.
  columns: Selected columns, or None for all.
  ```

- **Returns:**

  ```text
  Raw values with shape ``(rows, width)`` (or ``(0, 1)`` for a block without columns).
  ```

**Observed usage:**

1. [production caller: `_prepare_closed_window_with_prefix_cache`](../../../../simulation/environment/observations/schema.py#L372)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    decision = int(end)
    window_length = int(length)
    if block.ndim != 2:
        raw = closed_window_raw(block, starts, decision, window_length, columns=columns)
        return prepare_observation_feature_channels(raw, include_validity=include_validity), False

    selected_columns = None if columns is None else np.asarray(columns, dtype=np.int64)
    width = int(block.shape[1]) if selected_columns is None else int(selected_columns.size)
    visible_end = int(np.searchsorted(starts, decision, side="right")) if starts.size else 0
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `prepare_observation_feature_channels`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.observations.schema`

**Purpose:** Sanitize feature values and optionally append their finite-value mask.

**Exact API:** {py:obj}`simulation.environment.observations.schema.prepare_observation_feature_channels` · **Source:** [simulation/environment/observations/schema.py:61](../../../../simulation/environment/observations/schema.py#L61)

**Inputs and outputs:**

- **Args:**

  ```text
  values: Two-dimensional feature window.
  include_validity: Whether to append one finite-value indicator per feature.
  ```

- **Returns:**

  ```text
  Sanitized features, optionally concatenated with validity channels.
  ```

**Observed usage:**

1. [test fixture: `test_unavailable_active_distances_remain_nonfinite`](../../../../tests/unit/features/test_pd_context.py#L204)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        columns = [
            "ctx_asia_high_dist_atr",
            "ctx_london_high_dist_atr",
            "ctx_pd_mid_dist_atr",
        ]
        channels = prepare_observation_feature_channels(
            ctx.loc[[missing_atr_bar], columns].to_numpy(dtype=np.float32),
            include_validity=True,
        )
        np.testing.assert_array_equal(channels[0, :3], np.zeros(3, dtype=np.float32))
        np.testing.assert_array_equal(channels[0, 3:], np.zeros(3, dtype=np.float32))
```

2. [production caller: `policy_observation_at`](../../../../simulation/backtest/event_driven_backtest.py#L1196)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        if mtf_observation:
            if m1_columns.size:
                raw_sequence = raw_sequence[:, m1_columns]
            else:
                raw_sequence = np.full((raw_sequence.shape[0], 1), np.nan, dtype=np.float32)
        raw_sequence = prepare_observation_feature_channels(
            raw_sequence, include_validity=feature_validity_channels
        )
        sequence, sequence_mask = pad_observation_window(raw_sequence, obs_window)

        position = state.position
        position_direction = float(position.direction) if position is not None else 0.0
        open_pnl = float(state.account.open_pnl) if position is not None else 0.0
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `prepare_observation_feature_channels_many`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.observations.schema`

**Purpose:** ``prepare_observation_feature_channels`` for several windows in one pass.

**Exact API:** {py:obj}`simulation.environment.observations.schema.prepare_observation_feature_channels_many` · **Source:** [simulation/environment/observations/schema.py:475](../../../../simulation/environment/observations/schema.py#L475)

**Inputs and outputs:**

- **Args:**

  ```text
  values_list: Two-dimensional raw windows.
  include_validity: Whether to append per-feature finite-value channels.
  ```

- **Returns:**

  ```text
  Prepared windows, one per input, in order.
  ```

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
result = prepare_observation_feature_channels_many(values_list=..., include_validity=...)
```

**Lifecycle context:** This is a standalone API owned by the module shown above. Use its documented inputs, outputs, and failure behavior together with the linked domain guide.

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `run_starts`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.observations.schema`

**Purpose:** Index of the first row of each run of constant columns. NaN matches NaN.

**Exact API:** {py:obj}`simulation.environment.observations.schema.run_starts` · **Source:** [simulation/environment/observations/schema.py:121](../../../../simulation/environment/observations/schema.py#L121)

**Inputs and outputs:**

- **Args:**

  ```text
  block: Block used by the operation described above.
  ```

- **Returns:**

  ```text
  Array returned by ``run_starts``.
  ```

**Observed usage:**

1. [test fixture: `test_closed_m5_window_ends_on_the_candle_that_closed_at_1035`](../../../../tests/unit/simulation/test_environment/test_mtf_windows.py#L30)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_closed_m5_window_ends_on_the_candle_that_closed_at_1035() -> None:
    index = pd.date_range("2020-01-02 09:00", "2020-01-02 11:00", freq="1min")
    minute = index.hour * 60 + index.minute
    block = ((minute // 5) * 5).to_numpy(dtype=np.float64).reshape(-1, 1)
    decision = int(index.searchsorted(pd.Timestamp("2020-01-02 10:37")))
    window, mask = closed_window(block, run_starts(block), decision, 24)
    newest = window[mask > 0][-3:, 0]
    np.testing.assert_array_equal(newest, [10 * 60 + 25, 10 * 60 + 30, 10 * 60 + 35])
    assert not np.any(window == 10 * 60 + 40)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `sanitize_observation_values`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.observations.schema`

**Purpose:** Map invalid feature values to neutral zero before policy inference.

**Exact API:** {py:obj}`simulation.environment.observations.schema.sanitize_observation_values` · **Source:** [simulation/environment/observations/schema.py:45](../../../../simulation/environment/observations/schema.py#L45)

**Inputs and outputs:**

- **Args:**

  ```text
  values: Feature array that may contain NaN or infinite values.
  ```

- **Returns:**

  ```text
  Float32 array with invalid values replaced by zero.
  ```

**Observed usage:**

1. [production caller: `policy_observation_at`](../../../../simulation/backtest/event_driven_backtest.py#L1351)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            if pre_ny_by_date:
                day_key = pd.Timestamp(bar_times[index]).date()
                pre_ny_sequence = pre_ny_by_date.get(day_key)
            elif pre_ny_data is not None and len(pre_ny_data) > 0:
                row_index = min(int(index), len(pre_ny_data) - 1)
                flattened = sanitize_observation_values(
                    np.asarray(pre_ny_data.iloc[row_index].values, dtype=np.float32)
                )
                if flattened.size == seq_len * n_features:
                    pre_ny_sequence = flattened.reshape(seq_len, n_features)
                elif flattened.ndim == 2:
                    pre_ny_sequence = flattened.astype(np.float32, copy=False)

# … caller assertions omitted …
```

2. [production caller: `_get_observation`](../../../../simulation/environment/observations/runtime.py#L295)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                pre_ny_seq = self.pre_ny_by_date.get(day_key)
            elif self.pre_ny_data is not None and len(self.pre_ny_data) > 0:
                # Legacy: each row is a flattened (seq_len * n_features) vector
                current_idx = min(self.step_idx, len(self.pre_ny_data) - 1)
                flat = np.asarray(self.pre_ny_data.iloc[current_idx].values, dtype=np.float32)
                flat = sanitize_observation_values(flat)
                if flat.size == seq_len * n_feat:
                    pre_ny_seq = flat.reshape(seq_len, n_feat)
                elif flat.ndim == 2:
                    pre_ny_seq = flat.astype(np.float32, copy=False)

# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `split_obs_columns`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.observations.schema`

**Purpose:** Route timeframe-prefixed features to their own model stream.

**Exact API:** {py:obj}`simulation.environment.observations.schema.split_obs_columns` · **Source:** [simulation/environment/observations/schema.py:88](../../../../simulation/environment/observations/schema.py#L88)

**Inputs and outputs:**

- **Args:**

  ```text
  names: Items supplied for the names, in input order.
  timeframes: Items supplied for the timeframes, in input order.
  ```

- **Returns:**

  ```text
  Mapping from ``str`` keys to ``np.ndarray[Any, Any]]`` values.
  ```

**Observed usage:**

1. [production caller: `run_backtest`](../../../../simulation/backtest/event_driven_backtest.py#L1091)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                bars["session_id"].ne(bars["session_id"].shift()).fillna(True).to_numpy(dtype=bool)
            )
            session_start_indices = np.maximum.accumulate(
                np.where(session_boundaries, np.arange(len(bars), dtype=np.int64), 0)
            )
    m1_columns, htf_columns = split_obs_columns(observation_columns)
    missing_regime = [name for name in REGIME_FEATURES if name not in observation_columns]
    if regime_observation and missing_regime:
        raise ValueError(f"regime observation is missing required D1 features: {missing_regime}")
    regime_columns = np.asarray(
        [
# … caller assertions omitted …
```

2. [production caller: `_initialize_observation_arrays`](../../../../simulation/environment/observation_arrays_initialization.py#L303)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            self._news_labels = (
                bars["session"].to_numpy().astype(str)
                if "session" in bars.columns
                else np.full(len(bars), "all")
            )
        self._m1_idx, self._htf_idx = split_obs_columns(self._obs_columns)
        self.regime_observation = bool(regime_observation)
        self.regime_observation_schema = regime_observation_schema() if regime_observation else None
        self.trade_setup_actions = bool(trade_setup_actions)
        allowed_timeframes = set(trade_setup_candidate_timeframes)
        unknown_timeframes = allowed_timeframes - set(
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`

## `timeframe_starts`

**Kind:** function · **Status:** stable · **Owner:** `simulation.environment.observations.schema`

**Purpose:** Map completed timeframe candles to their first visible M1 decision row.

**Exact API:** {py:obj}`simulation.environment.observations.schema.timeframe_starts` · **Source:** [simulation/environment/observations/schema.py:142](../../../../simulation/environment/observations/schema.py#L142)

**Inputs and outputs:**

- **Args:**

  ```text
  index: Position or label identifying the requested item.
  timeframe: Text or path value identifying the timeframe.
  scheduled_closes: Key-value data used for the scheduled closes.
  session_start: Text or path value identifying the session start.
  ```

- **Returns:**

  ```text
  Array returned by ``timeframe_starts``.
  ```

**Observed usage:**

1. [test fixture: `test_timeframe_starts_preserve_equal_consecutive_candles`](../../../../tests/unit/simulation/test_environment/test_mtf_windows.py#L305)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_timeframe_starts_preserve_equal_consecutive_candles() -> None:
    index = pd.date_range("2020-01-02 09:00", "2020-01-02 11:00", freq="1min")
    starts = timeframe_starts(index, "M3")
    decision = int(index.searchsorted(pd.Timestamp("2020-01-02 10:37")))
    repeated_features = np.zeros((len(index), 1), dtype=np.float32)
    window, mask = closed_window(repeated_features, starts, decision, 4)

    np.testing.assert_array_equal(mask, np.ones(4, dtype=np.float32))
    np.testing.assert_array_equal(window[:, 0], np.zeros(4, dtype=np.float32))
    assert int(np.count_nonzero(starts <= decision)) == 32
```

2. [test fixture: `test_timeframe_starts_include_scheduled_short_candle_close`](../../../../tests/unit/simulation/test_environment/test_mtf_windows.py#L317)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_timeframe_starts_include_scheduled_short_candle_close() -> None:
    index = pd.date_range("2020-01-02 09:00", "2020-01-02 11:00", freq="1min")
    starts = timeframe_starts(
        index,
        "M5",
        {"2020-01-02": "10:37"},
        session_start="09:00",
    )

    assert pd.Timestamp("2020-01-02 10:37") in index[starts]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/trading`
- Generated package reference: {doc}`../../generated/simulation/index`
