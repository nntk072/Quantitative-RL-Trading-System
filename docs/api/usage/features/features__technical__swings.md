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

1. [test fixture: `test_swing_features_are_causal`](../../../../tests/unit/features/test_pivots_swings.py#L59)

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

2. [test fixture: `test_bars_since_last_swing_scales_by_obs_window`](../../../../tests/unit/features/test_pivots_swings.py#L336)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        index=idx,
    )
    feat = swing_features(
        bars,
        swings,
        classify_structure(swings),
        atr=pd.Series(1.0, index=idx),
        obs_window=60,
    )
    since = feat["bars_since_last_swing"]
    assert since.iloc[0] == pytest.approx(0.0)
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

1. [production caller: `smt_divergence`](../../../../features/context/smt.py#L32)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    sec_close = secondary["close"].reindex(primary.index, method="ffill")
    sec_aligned = secondary.reindex(primary.index, method="ffill")

    pr_piv = detect_pivots(primary, left=swing_period, right=swing_period)
    sec_piv = detect_pivots(sec_aligned, left=swing_period, right=swing_period)

    def _paired_divergences(
        primary_event: pd.Series,
        secondary_event: pd.Series,
# … caller assertions omitted …
```

2. [production caller: `_pivot_references`](../../../../features/technical/htf_sweeps.py#L103)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    bar_ends = bar_ends.loc[complete]
    if tf.empty:
        return []

    config = TIMEFRAME_CONFIG[timeframe]
    pivots = detect_pivots(tf, left=int(config["left"]), right=int(config["right"]))
    refs: list[_PivotReference] = []
    for side, event_col, price_col, loc_col in (
        ("high", "pivot_high_event", "pivot_high_extreme", "pivot_high_location"),
        ("low", "pivot_low_event", "pivot_low_extreme", "pivot_low_location"),
    ):
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
