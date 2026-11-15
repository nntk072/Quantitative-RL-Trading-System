# Features · `technical.swings`

This page contains 3 public callable records owned by `features.technical.swings`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `classify_structure`

**Kind:** function · **Status:** stable · **Owner:** `features.technical.swings`

**Purpose:** Classify accepted swings as HH/HL/LH/LL.

**Exact API:** {py:obj}`features.technical.swings.classify_structure` · **Source:** [features/technical/swings.py:222](../../../../features/technical/swings.py#L222)

**Inputs and outputs:**

- **Args:**

  ```text
  swings: Output of :func:`detect_swings`.
  ```

- **Returns:**

  ```text
  Frame with ``structure`` (string) plus one-hot HH/HL/LH/LL flags.
  ```

**Observed usage:**

1. [test fixture: `test_classify_structure_labels_new_highs_and_lows_against_prior_events`](../../../../tests/unit/features/test_pivots_swings.py#L48)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_classify_structure_labels_new_highs_and_lows_against_prior_events() -> None:
    result = classify_structure(_accepted_swings())

    assert result["structure"].tolist() == ["", "", "", "HH", "HL", "LH", "LL"]
    assert result["hh"].tolist() == [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    assert result["hl"].tolist() == [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert result["lh"].tolist() == [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    assert result["ll"].tolist() == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
```

2. [test fixture: `test_swing_features_are_causal`](../../../../tests/unit/features/test_pivots_swings.py#L101)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_swing_features_are_causal() -> None:
    bars = _pivot_bars()
    piv = detect_pivots(bars, left=2, right=2)
    swings = detect_swings(bars, piv, atr_mult=0.0)
    feat = swing_features(bars, swings, classify_structure(swings))
    trunc = bars.iloc[:8]
    piv_t = detect_pivots(trunc, left=2, right=2)
    sw_t = detect_swings(trunc, piv_t, atr_mult=0.0)
    feat_t = swing_features(trunc, sw_t, classify_structure(sw_t))
    overlap = feat_t.index[:6]
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `detect_pivots`

**Kind:** function · **Status:** stable · **Owner:** `features.technical.swings`

**Purpose:** Detect fractal pivots; features populate only from the confirmation bar.

**Exact API:** {py:obj}`features.technical.swings.detect_pivots` · **Source:** [features/technical/swings.py:26](../../../../features/technical/swings.py#L26)

**Inputs and outputs:**

- **Args:**

  ```text
  df: OHLC frame with a DatetimeIndex.
  left: Bars before the pivot that must be strictly lower/higher.
  right: Confirmation bars after the pivot.
  ```

- **Returns:**

  ```text
  Frame with pivot high/low event, price, extreme, and location columns.
  ```

**Observed usage:**

1. [tutorial example: `swings-liquidity-smt-po3-fvg-ifvg · code cell 2`](../../../../docs/subjects/B_market_structure_setups/examples/swings-liquidity-smt-po3-fvg-ifvg.ipynb)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
import pandas as pd

from features.po3.fvg_detection import FVGConfig, detect_fvg
from features.technical.swings import detect_pivots

idx = pd.date_range("2026-01-05 09:00", periods=8, freq="1min", tz="Etc/GMT-3")
bars = pd.DataFrame(
    {
        "open": [9.0, 10.0, 12.0, 11.0, 9.0, 11.0, 12.0, 12.0],
        "high": [10.0, 12.0, 13.0, 12.0, 11.0, 14.0, 15.0, 13.0],
        "low": [8.0, 11.0, 12.0, 10.0, 8.0, 13.0, 14.0, 12.0],
        "close": [9.0, 11.0, 12.5, 10.5, 9.0, 13.5, 14.5, 12.5],
    },
    index=idx,
)
pivots = detect_pivots(bars, left=1, right=1)
assert pivots.loc[idx[3], "pivot_high_event"]
assert pivots.loc[idx[3], "pivot_high_location"] == 2
assert not pivots.loc[idx[2], "pivot_high_event"]
fvgs = detect_fvg(bars, FVGConfig(min_imbalance_pts=1.0))
assert fvgs.loc[idx[2], "fvg_bullish"] == 1
assert fvgs.loc[idx[4], "fvg_bearish"] == 1
(
    pivots.loc[[idx[2], idx[3]], ["pivot_high_event", "pivot_high_location"]],
    fvgs[["fvg_bullish", "fvg_bearish"]],
)
```

2. [production caller: `smt_divergence`](../../../../features/context/smt.py#L33)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    sec_close = secondary["close"].reindex(primary.index, method="ffill")

    pr_piv = detect_pivots(primary, left=swing_period, right=swing_period)
    # Detect pivots only on observed secondary bars. Forward-filled OHLC rows
    # are useful for a synchronized close/spread, but they are not new bars and
    # must not count toward a fractal's left/right confirmation window.
    sec_piv = detect_pivots(secondary, left=swing_period, right=swing_period)
    primary_times_ns = pd.DatetimeIndex(primary.index).to_numpy(dtype="datetime64[ns]").view("i8")
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `detect_swings`

**Kind:** function · **Status:** stable · **Owner:** `features.technical.swings`

**Purpose:** ATR-filtered zigzag on confirmed pivots.

**Exact API:** {py:obj}`features.technical.swings.detect_swings` · **Source:** [features/technical/swings.py:86](../../../../features/technical/swings.py#L86)

**Inputs and outputs:**

- **Args:**

  ```text
  df: OHLC frame aligned with ``pivots``.
  pivots: Output of :func:`detect_pivots`.
  atr: ATR series; computed from ``df`` when None.
  atr_mult: Reversal threshold in ATR units.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``detect_swings``.
  ```

**Observed usage:**

1. [production caller: `structure_levels`](../../../../features/technical/structure.py#L74)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    pivots = detect_pivots(bars, left=swing_period, right=swing_period)
    swings = detect_swings(bars, pivots, atr_mult=atr_mult)
    times = np.asarray(bars.index, dtype="datetime64[ns]")
    loc_h = swings["swing_high_location"].to_numpy(dtype=float)
    loc_l = swings["swing_low_location"].to_numpy(dtype=float)
    sh_times = np.full(len(bars), np.datetime64("NaT"), dtype="datetime64[ns]")
    sl_times = np.full(len(bars), np.datetime64("NaT"), dtype="datetime64[ns]")
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
