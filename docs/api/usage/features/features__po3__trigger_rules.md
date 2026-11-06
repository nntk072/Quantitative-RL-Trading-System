# Features · `po3.trigger_rules`

This page contains 5 public callable records owned by `features.po3.trigger_rules`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `EntryConfig`

**Kind:** class · **Status:** stable · **Owner:** `features.po3.trigger_rules`

**Purpose:** Configuration for entry triggers.

**Exact API:** {py:obj}`features.po3.trigger_rules.EntryConfig` · **Source:** [features/po3/trigger_rules.py:16](../../../../features/po3/trigger_rules.py#L16)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `test_entry_trigger_with_custom_config`](../../../../tests/unit/features/test_po3_config.py#L210)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_entry_trigger_with_custom_config(self, sample_bars: pd.DataFrame) -> None:
    fvg_result = detect_fvg(sample_bars)
    ifvg_result = detect_ifvg_confirmation(sample_bars, fvg_result)
    config = EntryConfig(retest_threshold=0.05)
    entry_result = detect_entry_trigger(sample_bars, ifvg_result, config=config)
    assert isinstance(entry_result, pd.DataFrame)
```

2. [test fixture: `test_retest_requires_a_bar_after_confirmation`](../../../../tests/unit/features/test_po3_config.py#L231)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                "ifvg_bullish_high": [12.0, 12.0],
            },
            index=idx,
        )

        entry = detect_entry_trigger(bars, ifvg, config=EntryConfig(retest_threshold=0.2))

        assert entry["entry_long"].tolist() == [0, 1]
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `detect_entry_trigger`

**Kind:** function · **Status:** stable · **Owner:** `features.po3.trigger_rules`

**Purpose:** Detect entry triggers based on IFVG confirmation.

**Exact API:** {py:obj}`features.po3.trigger_rules.detect_entry_trigger` · **Source:** [features/po3/trigger_rules.py:31](../../../../features/po3/trigger_rules.py#L31)

**Inputs and outputs:**

- **Args:**

  ```text
  bars (pd.DataFrame): OHLC DataFrame with 'high', 'low', 'close' columns.
  ifvg_df (pd.DataFrame): IFVG confirmation output from detect_ifvg_confirmation().
  entry_type (EntryTriggerType): Type of entry trigger to detect.
  config (EntryConfig, optional): Configuration for entry detection. Uses defaults if None.
  ```

- **Returns:**

  ```text
  pd.DataFrame: DataFrame with same index, containing:
      - entry_long: 1 if long entry trigger detected
      - entry_short: 1 if short entry trigger detected
      - entry_trigger_type: Type of trigger ('retest', 'ltf_fvg', 'close_through')
  ```

**Observed usage:**

1. [test fixture: `test_entry_trigger_returns_expected_columns`](../../../../tests/unit/features/test_po3_config.py#L172)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_entry_trigger_returns_expected_columns(self, sample_bars: pd.DataFrame) -> None:
    fvg_result = detect_fvg(sample_bars)
    ifvg_result = detect_ifvg_confirmation(sample_bars, fvg_result)
    entry_result = detect_entry_trigger(sample_bars, ifvg_result)
    assert "entry_long" in entry_result.columns
    assert "entry_short" in entry_result.columns
    assert "entry_trigger_type" in entry_result.columns
```

2. [test fixture: `test_entry_trigger_output_shape`](../../../../tests/unit/features/test_po3_config.py#L181)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_entry_trigger_output_shape(self, sample_bars: pd.DataFrame) -> None:
    fvg_result = detect_fvg(sample_bars)
    ifvg_result = detect_ifvg_confirmation(sample_bars, fvg_result)
    entry_result = detect_entry_trigger(sample_bars, ifvg_result)
    assert len(entry_result) == len(sample_bars)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `detect_htf_fvg`

**Kind:** function · **Status:** stable · **Owner:** `features.po3.trigger_rules`

**Purpose:** Detect FVG on higher timeframe and map back to M1 bars.

**Exact API:** {py:obj}`features.po3.trigger_rules.detect_htf_fvg` · **Source:** [features/po3/trigger_rules.py:210](../../../../features/po3/trigger_rules.py#L210)

**Inputs and outputs:**

- **Args:**

  ```text
  m1_bars (pd.DataFrame): M1 OHLC DataFrame with DatetimeIndex.
  htf (str): Higher timeframe label (e.g., 'M5', 'M10', 'M15', 'M30', 'H1').
  config (FVGConfig, optional): Configuration for FVG detection. Uses defaults if None.
  timeframe_bars: Optional precomputed higher-timeframe bars, avoiding resampling.
  availability_times: Optional timestamps controlling when each HTF value becomes observable.
  ```

- **Returns:**

  ```text
  pd.DataFrame: DataFrame with same index as M1 input, containing:
      - htf_fvg_bullish: 1 if bullish FVG detected on HTF
      - htf_fvg_bearish: 1 if bearish FVG detected on HTF
      - htf_fvg_bullish_low: Low price of HTF FVG zone
      - htf_fvg_bullish_high: High price of HTF FVG zone
      - htf_fvg_bearish_low: Low price of HTF FVG zone
      - htf_fvg_bearish_high: High price of HTF FVG zone
  ```

**Observed usage:**

1. [test fixture: `test_htf_fvg_returns_expected_columns`](../../../../tests/unit/features/test_po3_config.py#L299)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_htf_fvg_returns_expected_columns(self, sample_bars: pd.DataFrame) -> None:
    result = detect_htf_fvg(sample_bars, htf="M5")
    assert "htf_fvg_bullish" in result.columns
    assert "htf_fvg_bearish" in result.columns
    assert "htf_fvg_bullish_low" in result.columns
    assert "htf_fvg_bullish_high" in result.columns
    assert "htf_fvg_bearish_low" in result.columns
    assert "htf_fvg_bearish_high" in result.columns
```

2. [test fixture: `test_htf_fvg_output_shape`](../../../../tests/unit/features/test_po3_config.py#L309)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_htf_fvg_output_shape(self, sample_bars: pd.DataFrame) -> None:
    result = detect_htf_fvg(sample_bars, htf="M5")
    assert len(result) == len(sample_bars)
    assert result.index.equals(sample_bars.index)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `detect_ltf_ifvg`

**Kind:** function · **Status:** stable · **Owner:** `features.po3.trigger_rules`

**Purpose:** Detect IFVG on lower timeframe and map back to primary timeframe bars.

**Exact API:** {py:obj}`features.po3.trigger_rules.detect_ltf_ifvg` · **Source:** [features/po3/trigger_rules.py:289](../../../../features/po3/trigger_rules.py#L289)

**Inputs and outputs:**

- **Args:**

  ```text
  m1_bars (pd.DataFrame): M1 OHLC DataFrame with DatetimeIndex.
  primary_tf (str): Primary timeframe label (e.g., 'M5', 'M10', 'M15', 'M30').
  ltf (str): Lower timeframe label (e.g., 'M1'). Default is 'M1'.
  fvg_config (FVGConfig, optional): Configuration for FVG detection. Uses defaults if None.
  ifvg_config (IFVGConfig, optional): Configuration for IFVG confirmation. Uses defaults if None.
  timeframe_bars: Optional precomputed primary-timeframe bars.
  availability_times: Optional timestamps controlling when each confirmation becomes observable.
  ```

- **Returns:**

  ```text
  pd.DataFrame: DataFrame with same index as M1 input, containing:
      - ltf_ifvg_bullish_confirmed: 1 if bullish IFVG confirmed on LTF
      - ltf_ifvg_bearish_confirmed: 1 if bearish IFVG confirmed on LTF
      - ltf_ifvg_bullish_low: Low price of LTF IFVG zone
      - ltf_ifvg_bullish_high: High price of LTF IFVG zone
      - ltf_ifvg_bearish_low: Low price of LTF IFVG zone
      - ltf_ifvg_bearish_high: High price of LTF IFVG zone
  ```

**Observed usage:**

1. [test fixture: `test_ltf_ifvg_returns_expected_columns`](../../../../tests/unit/features/test_po3_config.py#L338)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_ltf_ifvg_returns_expected_columns(self, sample_bars: pd.DataFrame) -> None:
    result = detect_ltf_ifvg(sample_bars, primary_tf="M5")
    assert "ltf_ifvg_bullish_confirmed" in result.columns
    assert "ltf_ifvg_bearish_confirmed" in result.columns
    assert "ltf_ifvg_bullish_low" in result.columns
    assert "ltf_ifvg_bullish_high" in result.columns
    assert "ltf_ifvg_bearish_low" in result.columns
    assert "ltf_ifvg_bearish_high" in result.columns
```

2. [test fixture: `test_ltf_ifvg_output_shape`](../../../../tests/unit/features/test_po3_config.py#L348)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_ltf_ifvg_output_shape(self, sample_bars: pd.DataFrame) -> None:
    result = detect_ltf_ifvg(sample_bars, primary_tf="M5")
    assert len(result) == len(sample_bars)
    assert result.index.equals(sample_bars.index)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `detect_po3_entries`

**Kind:** function · **Status:** stable · **Owner:** `features.po3.trigger_rules`

**Purpose:** Unified PO3 entry detection combining HTF FVG, LTF IFVG, and entry triggers.

**Exact API:** {py:obj}`features.po3.trigger_rules.detect_po3_entries` · **Source:** [features/po3/trigger_rules.py:372](../../../../features/po3/trigger_rules.py#L372)

**Inputs and outputs:**

- **Args:**

  ```text
  m1_bars (pd.DataFrame): M1 OHLC DataFrame with DatetimeIndex.
  htf (str): Higher timeframe for FVG detection (default: 'M15').
  primary_tf (str): Primary timeframe for IFVG confirmation (default: 'M5').
  entry_type (EntryTriggerType): Type of entry trigger: 'retest', 'close_through', or 'ltf_fvg'.
  fvg_config (FVGConfig, optional): Configuration for FVG detection.
  ifvg_config (IFVGConfig, optional): Configuration for IFVG confirmation.
  entry_config (EntryConfig, optional): Configuration for entry triggers.
  timeframe_bars: Optional precomputed bars keyed by timeframe.
  availability_times: Optional per-timeframe availability timestamps for causal alignment.
  ```

- **Returns:**

  ```text
  pd.DataFrame: DataFrame with same index as M1 input, containing:
      - All HTF FVG columns
      - All LTF IFVG columns
      - entry_long: 1 if long entry signal
      - entry_short: 1 if short entry signal
      - entry_trigger_type: Type of entry trigger that fired
  ```

**Observed usage:**

1. [test fixture: `po3_signals`](../../../../tests/unit/evaluation/test_po3_plots.py#L42)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def po3_signals(signal_bars: pd.DataFrame) -> pd.DataFrame:
    return detect_po3_entries(signal_bars, htf="M15", primary_tf="M5")
```

2. [test fixture: `test_plot_window_keeps_lookback_for_zones`](../../../../tests/unit/evaluation/test_po3_plots.py#L157)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_plot_window_keeps_lookback_for_zones(signal_bars: pd.DataFrame, tmp_path) -> None:
    start = signal_bars.index[100]
    end = signal_bars.index[150]
    signals = detect_po3_entries(signal_bars, htf="M15", primary_tf="M5")
    fig = plot_fvg_signals(
        signal_bars,
        signals,
        window=(start, end),
        candle_tf="1min",
        out_path=tmp_path / "win.png",
        dpi=80,
    )
    assert len(fig.axes) == 1
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
