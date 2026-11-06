# Market data · `transforms.resample`

This page contains 1 public callable records owned by `market_data.transforms.resample`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `resample`

**Kind:** function · **Status:** stable · **Owner:** `market_data.transforms.resample`

**Purpose:** Return *tf* bars built from *m1* (1-minute) bars.

**Exact API:** {py:obj}`market_data.transforms.resample.resample` · **Source:** [market_data/transforms/resample.py:39](../../../../market_data/transforms/resample.py#L39)

**Inputs and outputs:**

- **Args:**

  ```text
  m1: DataFrame produced by :func:`market_data.loading.bars.load_bars`
      with a DatetimeIndex.
  tf: Target timeframe string.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``resample``.
  ```

**Observed usage:**

1. [test fixture: `test_m10_resample_aggregates_ten_left_closed_m1_bars`](../../../../tests/integration/test_resample_m10.py#L24)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "spread": [0.5] * 20,
        },
        index=index,
    )

    m10 = resample(m1, "M10")

    assert m10.index.equals(index[[0, 10]])
    assert m10.iloc[0].to_dict() == {
        "open": 0.0,
        "high": 11.0,
# … caller assertions omitted …
```

2. [test fixture: `test_partial_resampled_bar_is_visible_only_at_close_and_first_later_m1`](../../../../tests/integration/test_resample_m10.py#L64)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "2025-01-02 09:10",
        ],
        tz=timezone,
    )
    m1 = pd.DataFrame({"open": range(5), "close": [10, 11, 14, 16, 20]}, index=index)
    m5 = resample(m1, "M5")
    close_times = timeframe_close_times(m5, "M5")
    aligned = align_timeframes(m1, {"M5": m5}, availability_times={"M5": close_times})

    assert m5.loc[index[0], "close"] == 14
    assert pd.isna(aligned.loc[index[2], "M5_close"])
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
