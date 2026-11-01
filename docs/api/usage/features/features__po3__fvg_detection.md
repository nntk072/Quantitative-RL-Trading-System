# Features · `po3.fvg_detection`

This page contains 2 public callable records owned by `features.po3.fvg_detection`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `FVGConfig`

**Kind:** class · **Status:** stable · **Owner:** `features.po3.fvg_detection`

**Purpose:** Configuration for FVG detection.

**Exact API:** {py:obj}`features.po3.fvg_detection.FVGConfig` · **Source:** [features/po3/fvg_detection.py:9](../../../../features/po3/fvg_detection.py#L9)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `test_fvg_with_custom_config`](../../../../tests/unit/features/test_po3_config.py#L63)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fvg_with_custom_config(self, sample_bars: pd.DataFrame) -> None:
    config = FVGConfig(min_imbalance_pts=0.5)
    result = detect_fvg(sample_bars, config=config)
    assert isinstance(result, pd.DataFrame)
```

2. [test fixture: `test_fvg_buffer_fraction_is_not_forced_to_ten_percent`](../../../../tests/unit/features/test_po3_config.py#L135)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_fvg_buffer_fraction_is_not_forced_to_ten_percent(self) -> None:
    config = FVGConfig(reaction_buffer_fraction=0.0)

    assert config.reaction_buffer_fraction == 0.0
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `detect_fvg`

**Kind:** function · **Status:** stable · **Owner:** `features.po3.fvg_detection`

**Purpose:** Detect Fair Value Gaps (FVG) using 3-bar imbalance rule.

**Exact API:** {py:obj}`features.po3.fvg_detection.detect_fvg` · **Source:** [features/po3/fvg_detection.py:25](../../../../features/po3/fvg_detection.py#L25)

**Inputs and outputs:**

- **Args:**

  ```text
  bars (pd.DataFrame): OHLC DataFrame with 'high', 'low', 'close' columns and DatetimeIndex.
  config (FVGConfig, optional): Configuration for FVG detection. Uses defaults if None.
  ```

- **Returns:**

  ```text
  pd.DataFrame: DataFrame with same index as input, containing:
      - fvg_bullish: 1 if bullish FVG detected at this bar, else 0
      - fvg_bearish: 1 if bearish FVG detected at this bar, else 0
      - fvg_bullish_low: Low price of the FVG zone (for bullish)
      - fvg_bullish_high: High price of the FVG zone (for bullish)
      - fvg_bearish_low: Low price of the FVG zone (for bearish)
      - fvg_bearish_high: High price of the FVG zone (for bearish)
  ```

**Observed usage:**

1. [test fixture: `test_static_plot_with_plain_fvg`](../../../../tests/unit/evaluation/test_po3_plots.py#L106)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_static_plot_with_plain_fvg(signal_bars: pd.DataFrame, tmp_path) -> None:
    fvg = detect_fvg(signal_bars)
    fig = plot_fvg_signals(signal_bars, fvg, candle_tf="5min", out_path=tmp_path / "fvg.png")
    assert len(fig.axes) == 1
```

2. [test fixture: `test_detect_fvg_returns_expected_columns`](../../../../tests/unit/features/test_po3_config.py#L47)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_detect_fvg_returns_expected_columns(self, sample_bars: pd.DataFrame) -> None:
    result = detect_fvg(sample_bars)
    assert "fvg_bullish" in result.columns
    assert "fvg_bearish" in result.columns
    assert "fvg_bullish_low" in result.columns
    assert "fvg_bullish_high" in result.columns
    assert "fvg_bearish_low" in result.columns
    assert "fvg_bearish_high" in result.columns
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
