# Features · `technical.indicators`

This page contains 2 public callable records owned by `features.technical.indicators`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `atr`

**Kind:** function · **Status:** stable · **Owner:** `features.technical.indicators`

**Purpose:** Calculate the exponentially smoothed average true range.

**Exact API:** {py:obj}`features.technical.indicators.atr` · **Source:** [features/technical/indicators.py:111](../../../../features/technical/indicators.py#L111)

**Inputs and outputs:**

- **Args:**

  ```text
  df: OHLC data with high, low, and close columns.
  period: Smoothing period used for the true range.
  ```

- **Returns:**

  ```text
  A series named atr aligned to the input index.
  ```

**Observed usage:**

1. [test fixture: `test_atr_function`](../../../../tests/integration/test_session_levels_integration.py#L78)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_atr_function(self, full_day_data: pd.DataFrame) -> None:
    atr_series = atr(full_day_data, period=14)
    assert len(atr_series) == len(full_day_data)
    assert atr_series.notna().sum() > 0
```

2. [tutorial example: `technical-indicators · code cell 2`](../../../../docs/subjects/A_data_features/examples/technical-indicators.ipynb)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
import pandas as pd

from features.technical.indicators import atr, ema, rsi

idx = pd.RangeIndex(12)
close = pd.Series(
    [10.0, 10.5, 10.2, 10.8, 11.0, 10.7, 11.3, 11.6, 11.2, 12.0, 12.3, 12.1], index=idx
)
full = ema(close, span=3)
short = ema(close.iloc[:8], span=3)
pd.testing.assert_series_equal(full.iloc[:8], short)
assert rsi(close, period=3).index.equals(close.index)
ohlc = pd.DataFrame({"high": close + 0.2, "low": close - 0.2, "close": close})
assert atr(ohlc, period=3).index.equals(close.index)
full.tail()
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `build_indicators`

**Kind:** function · **Status:** stable · **Owner:** `features.technical.indicators`

**Purpose:** Compute all indicators and return a wide feature DataFrame.

**Exact API:** {py:obj}`features.technical.indicators.build_indicators` · **Source:** [features/technical/indicators.py:484](../../../../features/technical/indicators.py#L484)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Cleaned, session-filtered M1 bars with a timezone-aware index.
  cfg: OmegaConf ``features`` sub-config.
  ```

- **Returns:**

  ```text
  A DataFrame containing the configured causal technical features.
  ```

**Observed usage:**

1. [test fixture: `_expected_htf_value`](../../../../tests/unit/features/test_htf_alignment.py#L52)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def _expected_htf_value(
    tf: str, col: str, t: pd.Timestamp, m1_bars: pd.DataFrame, feat_cfg
) -> float:
    htf = build_indicators(resample(m1_bars, tf), feat_cfg)  # type: ignore[arg-type]
    completed = htf.shift(1)
    eligible = completed.loc[completed.index <= t]
    assert not eligible.empty, f"no completed {tf} bar at or before {t}"
    return float(eligible[col].iloc[-1])
```

2. [test fixture: `test_htf_alignment_causal_open_time`](../../../../tests/unit/features/test_htf_alignment.py#L268)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_htf_alignment_causal_open_time(m1_bars, feat_cfg):
    from market_data.transforms.align import align_timeframes

    for tf in HTF_TFS:
        htf = build_indicators(resample(m1_bars, tf), feat_cfg)  # type: ignore[arg-type]
        aligned = align_timeframes(m1_bars[["close"]], {tf: htf[["ema_9"]]})[f"{tf}_ema_9"]
        for t in m1_bars.index[300::100]:
            expected = _expected_htf_value(tf, "ema_9", t, m1_bars, feat_cfg)
            if np.isnan(expected):
                continue
            assert abs(aligned.loc[t] - expected) < 1e-9, (
                f"{tf} value at {t} not from last completed bar"
            )
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
