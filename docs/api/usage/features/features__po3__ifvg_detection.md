# Features · `po3.ifvg_detection`

This page contains 2 public callable records owned by `features.po3.ifvg_detection`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `IFVGConfig`

**Kind:** class · **Status:** stable · **Owner:** `features.po3.ifvg_detection`

**Purpose:** Configuration for IFVG confirmation.

**Exact API:** {py:obj}`features.po3.ifvg_detection.IFVGConfig` · **Source:** [features/po3/ifvg_detection.py:19](../../../../features/po3/ifvg_detection.py#L19)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `test_ifvg_with_custom_config`](../../../../tests/unit/features/test_po3_config.py#L99)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_ifvg_with_custom_config(self, sample_bars: pd.DataFrame) -> None:
    fvg_result = detect_fvg(sample_bars)
    config = IFVGConfig(close_through_threshold=0.3)
    ifvg_result = detect_ifvg_confirmation(sample_bars, fvg_result, config=config)
    assert isinstance(ifvg_result, pd.DataFrame)
```

2. [test fixture: `test_optional_buffer_can_be_enabled_or_disabled`](../../../../tests/unit/features/test_po3_config.py#L117)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        fvg = detect_fvg(bars)

        enabled = detect_ifvg_confirmation(
            bars,
            fvg,
            IFVGConfig(close_through_threshold=0.1, close_through_buffer_enabled=True),
        )
        disabled = detect_ifvg_confirmation(
            bars,
            fvg,
            IFVGConfig(close_through_threshold=0.1, close_through_buffer_enabled=False),
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `detect_ifvg_confirmation`

**Kind:** function · **Status:** stable · **Owner:** `features.po3.ifvg_detection`

**Purpose:** Detect IFVG (Imbalanced FVG) confirmation.

**Exact API:** {py:obj}`features.po3.ifvg_detection.detect_ifvg_confirmation` · **Source:** [features/po3/ifvg_detection.py:44](../../../../features/po3/ifvg_detection.py#L44)

**Inputs and outputs:**

- **Args:**

  ```text
  bars (pd.DataFrame): OHLC DataFrame with 'high', 'low', 'close' columns.
  fvg_df (pd.DataFrame): FVG detection output from detect_fvg().
  config (IFVGConfig, optional): Configuration for IFVG confirmation. Uses defaults if None.
  ```

- **Returns:**

  ```text
  pd.DataFrame: DataFrame with same index, containing:
      - ifvg_bullish_confirmed: 1 if bullish IFVG confirmed at this bar
      - ifvg_bearish_confirmed: 1 if bearish IFVG confirmed at this bar
      - ifvg_bullish_low: Low price of the IFVG zone (for bullish)
      - ifvg_bullish_high: High price of the IFVG zone (for bullish)
      - ifvg_bearish_low: Low price of the IFVG zone (for bearish)
      - ifvg_bearish_high: High price of the IFVG zone (for bearish)
  ```

**Observed usage:**

1. [test fixture: `test_ifvg_returns_expected_columns`](../../../../tests/unit/features/test_po3_config.py#L80)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_ifvg_returns_expected_columns(self, sample_bars: pd.DataFrame) -> None:
    fvg_result = detect_fvg(sample_bars)
    ifvg_result = detect_ifvg_confirmation(sample_bars, fvg_result)
    assert "ifvg_bullish_confirmed" in ifvg_result.columns
    assert "ifvg_bearish_confirmed" in ifvg_result.columns
    assert "ifvg_bullish_low" in ifvg_result.columns
    assert "ifvg_bullish_high" in ifvg_result.columns
    assert "ifvg_bearish_low" in ifvg_result.columns
    assert "ifvg_bearish_high" in ifvg_result.columns
    assert "ifvg_bullish_origin_bar" in ifvg_result.columns
    assert "ifvg_bearish_origin_bar" in ifvg_result.columns
```

2. [test fixture: `test_ifvg_output_shape`](../../../../tests/unit/features/test_po3_config.py#L93)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_ifvg_output_shape(self, sample_bars: pd.DataFrame) -> None:
    fvg_result = detect_fvg(sample_bars)
    ifvg_result = detect_ifvg_confirmation(sample_bars, fvg_result)
    assert len(ifvg_result) == len(sample_bars)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
