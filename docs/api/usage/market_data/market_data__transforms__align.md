# Market data · `transforms.align`

This page contains 2 public callable records owned by `market_data.transforms.align`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `align_timeframes`

**Kind:** function · **Status:** stable · **Owner:** `market_data.transforms.align`

**Purpose:** Merge higher-TF DataFrames into the M1 spine causally.

**Exact API:** {py:obj}`market_data.transforms.align.align_timeframes` · **Source:** [market_data/transforms/align.py:83](../../../../market_data/transforms/align.py#L83)

**Inputs and outputs:**

- **Args:**

  ```text
  m1: M1 DataFrame (reference spine); must have a tz-aware DatetimeIndex.
  higher: Dict mapping timeframe label (e.g. ``"M5"``) to the corresponding
      bar DataFrame.
  prefix: Optional column prefix (e.g. symbol name).
  completed_bars: If True (default), ``shift(1)`` before ffill.
  availability_times: Optional per-timeframe close timestamps indexed like ``higher[tf]``.
      A feature becomes visible on the M1 spine at its close timestamp. This
      handles gaps and shortened final bars without using the next observed
      HTF row as a proxy for the close.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``align_timeframes``.
  ```

**Observed usage:**

1. [test fixture: `test_higher_timeframe_value_appears_only_at_its_close`](../../../../tests/unit/features/test_alignment_properties.py#L30)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        periods=source_count + 1,
        freq=pd.Timedelta(minutes=minutes_per_bar),
    )
    m1 = pd.DataFrame({"minute": np.arange(len(m1_index))}, index=m1_index)
    higher = pd.DataFrame({"signal": np.arange(source_count + 1, dtype=float)}, index=source_index)
    aligned = align_timeframes(m1, {f"M{minutes_per_bar}": higher})

    for minute, timestamp in enumerate(m1_index):
        completed_count = min(minute // minutes_per_bar, source_count)
        observed = aligned.loc[timestamp, f"M{minutes_per_bar}_signal"]
        if completed_count == 0:
# … caller assertions omitted …
```

2. [test fixture: `test_empty_higher_timeframe_does_not_add_empty_columns`](../../../../tests/unit/features/test_alignment_properties.py#L71)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_empty_higher_timeframe_does_not_add_empty_columns() -> None:
    index = pd.date_range("2025-01-06 00:00", periods=2, freq="min", tz="UTC")
    m1 = pd.DataFrame({"close": [10.0, 11.0]}, index=index)
    empty = pd.DataFrame({"signal": pd.Series(dtype=float)})

    aligned = align_timeframes(m1, {"M5": empty})

    pd.testing.assert_frame_equal(aligned, m1)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `timeframe_close_times`

**Kind:** function · **Status:** stable · **Owner:** `market_data.transforms.align`

**Purpose:** Return bar close timestamps from open-stamped bars and the session calendar.

**Exact API:** {py:obj}`market_data.transforms.align.timeframe_close_times` · **Source:** [market_data/transforms/align.py:25](../../../../market_data/transforms/align.py#L25)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Market bars to process.
  timeframe: Text or path value identifying the timeframe.
  scheduled_closes: Key-value data used for the scheduled closes.
  session_start: Text or path value identifying the session start.
  ```

- **Returns:**

  ```text
  Result of return bar close timestamps from open-stamped bars and the session calendar.
  ```

**Observed usage:**

1. [test fixture: `test_timeframe_close_times_clip_a_short_session_final_bar`](../../../../tests/unit/features/test_alignment_properties.py#L80)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_timeframe_close_times_clip_a_short_session_final_bar() -> None:
    index = pd.DatetimeIndex([pd.Timestamp("2025-01-06 16:58", tz="UTC")])
    bars = pd.DataFrame({"close": [100.0]}, index=index)

    closes = timeframe_close_times(
        bars,
        "M5",
        scheduled_closes={"2025-01-06": "17:00"},
    )

    assert closes.iloc[0] == pd.Timestamp("2025-01-06 17:00", tz="UTC")
```

2. [test fixture: `test_timeframe_close_times_reject_unsupported_timeframes`](../../../../tests/unit/features/test_alignment_properties.py#L93)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_timeframe_close_times_reject_unsupported_timeframes() -> None:
    bars = pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC"))

    with pytest.raises(ValueError, match="unsupported timeframe"):
        timeframe_close_times(bars, "M2")
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
