# Features · `po3.ifvg_detection`

This page contains 2 public callable records owned by `features.po3.ifvg_detection`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `IFVGConfig`

**Kind:** class · **Status:** stable · **Owner:** `features.po3.ifvg_detection`

**Purpose:** Configuration for IFVG confirmation.

**Exact API:** {py:obj}`features.po3.ifvg_detection.IFVGConfig` · **Source:** [features/po3/ifvg_detection.py:19](../../../../features/po3/ifvg_detection.py#L19)

**Inputs and outputs:**

**Observed usage:**

1. [test fixture: `test_ifvg_with_custom_config`](../../../../tests/unit/features/test_po3_config.py#L103)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_ifvg_with_custom_config(self, sample_bars: pd.DataFrame) -> None:
    fvg_result = detect_fvg(sample_bars)
    config = IFVGConfig(close_through_threshold=0.3)
    ifvg_result = detect_ifvg_confirmation(sample_bars, fvg_result, config=config)
    assert isinstance(ifvg_result, pd.DataFrame)
```

2. [test fixture: `test_optional_buffer_can_be_enabled_or_disabled`](../../../../tests/unit/features/test_po3_config.py#L121)

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

**Purpose:** Return the existing scalar newest-confirmation-per-side feature view.

**Exact API:** {py:obj}`features.po3.ifvg_detection.detect_ifvg_confirmation` · **Source:** [features/po3/ifvg_detection.py:251](../../../../features/po3/ifvg_detection.py#L251)

**Inputs and outputs:**

- **Args:**

  ```text
  bars: Chronological OHLC bars used to confirm inversion events.
  fvg_df: Fair-value-gap features aligned with ``bars``.
  config: Optional IFVG detection settings.
  ```

- **Returns:**

  ```text
  Scalar feature frame containing the newest confirmed inversion by side.
  ```

**Observed usage:**

1. [test fixture: `test_zone_ledger_reconciles_scalar_selection_and_monthly_suppression`](../../../../tests/research/test_ifvg_zone_event_ledger.py#L31)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_zone_ledger_reconciles_scalar_selection_and_monthly_suppression() -> None:
    bars = _two_same_row_bullish_confirmations()
    fvg = detect_fvg(bars)
    scalar = detect_ifvg_confirmation(bars, fvg)
    ledger = detect_ifvg_confirmation_events(bars, fvg)

    _validate_scalar_projection(ledger, scalar)
    collisions = _collision_table(ledger, bars)
    monthly = _monthly_summary(ledger, bars)
# … caller assertions omitted …
```

2. [test fixture: `test_ifvg_returns_expected_columns`](../../../../tests/unit/features/test_po3_config.py#L84)

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

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
