# Features · `po3.zones`

This page contains 3 public callable records owned by `features.po3.zones`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `FVGZone`

**Kind:** class · **Status:** stable · **Owner:** `features.po3.zones`

**Purpose:** A drawable FVG/IFVG zone rectangle.

**Exact API:** {py:obj}`features.po3.zones.FVGZone` · **Source:** [features/po3/zones.py:33](../../../../features/po3/zones.py#L33)

**Inputs and outputs:**

**Observed usage:**

1. [production caller: `build_fvg_zones`](../../../../features/po3/zones.py#L118)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                    invalidated = True
                    end_ts = bars.index[j]
                    break

            zones.append(
                FVGZone(
                    kind=kind,
                    side=side,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    zone_low=float(zone_low),
                    zone_high=float(zone_high),
                    confirmed=(kind == "ltf_ifvg"),
                    invalidated=invalidated,
                )
            )

    zones.sort(key=lambda z: z.start_ts)
    return zones
```

2. [production caller: `build_fvg_zones_for_plot`](../../../../features/po3/zones.py#L227)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                    start_i=i,
                    zone_low=zone_low,
                    zone_high=zone_high,
                )
                zones.append(
                    FVGZone(
                        kind="htf_fvg",
                        side=side,
                        start_ts=start_ts,
                        end_ts=end_ts,
                        zone_low=zone_low,
                        zone_high=zone_high,
                        confirmed=False,
                        invalidated=invalidated,
                    )
                )

                # --- LTF IFVG: start at confirmation candle on LTF ---
    ltf_bars = resample(m1_bars, ltf)  # type: ignore[arg-type]
    if len(ltf_bars) >= 3:
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `build_fvg_zones`

**Kind:** function · **Status:** stable · **Owner:** `features.po3.zones`

**Purpose:** Build drawable zone rectangles from PO3 signal columns.

**Exact API:** {py:obj}`features.po3.zones.build_fvg_zones` · **Source:** [features/po3/zones.py:58](../../../../features/po3/zones.py#L58)

**Inputs and outputs:**

- **Args:**

  ```text
  bars (pd.DataFrame): M1 OHLC bars (DatetimeIndex, 'high'/'low' columns) that produced the signals.
  signals (pd.DataFrame): Output of :func:`detect_htf_fvg`, :func:`detect_ltf_ifvg`, or the
      combined output of :func:`detect_po3_entries`.  Must share the index of
      ``bars`` and contain a subset of the well-known column names.
  max_zone_bars (int): Maximum number of bars a zone stays active before it is considered expired.
  ```

- **Returns:**

  ```text
  list[FVGZone]: One zone per formation event, ordered by start timestamp.
  ```

**Observed usage:**

1. [test fixture: `test_zone_from_htf_fvg`](../../../../tests/unit/features/test_po3_config.py#L594)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_zone_from_htf_fvg(self, fvg_bars: pd.DataFrame) -> None:
    signals = detect_htf_fvg(fvg_bars, htf="M5")
    zones = build_fvg_zones(fvg_bars, signals)
    bullish = [z for z in zones if z.side == "bullish"]
    assert len(bullish) >= 1
    z = bullish[0]
    assert z.kind == "htf_fvg"
    assert z.confirmed is False
    assert z.zone_low == 11.0
    assert z.zone_high == 12.0
    assert z.start_ts < z.end_ts
```

2. [test fixture: `test_zone_edge_dedup`](../../../../tests/unit/features/test_po3_config.py#L607)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_zone_edge_dedup(self, fvg_bars: pd.DataFrame) -> None:
    signals = detect_htf_fvg(fvg_bars, htf="M5")
    zones = build_fvg_zones(fvg_bars, signals)
    starts = [z.start_ts for z in zones if z.side == "bullish"]
    # The M5 H4 bar where FVG fires is one contiguous run -> 1 start.
    assert len(starts) <= 3
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`

## `build_fvg_zones_for_plot`

**Kind:** function · **Status:** stable · **Owner:** `features.po3.zones`

**Purpose:** Build drawable FVG/IFVG zones from native HTF/LTF candles (plot-only).

**Exact API:** {py:obj}`features.po3.zones.build_fvg_zones_for_plot` · **Source:** [features/po3/zones.py:165](../../../../features/po3/zones.py#L165)

**Inputs and outputs:**

- **Args:**

  ```text
  m1_bars: One-minute OHLCV bars used to build the sequences.
  htf: Text or path value identifying the htf.
  ltf: Text or path value identifying the ltf.
  fvg_config: Fvg config used by the operation described above.
  ifvg_config: Ifvg config used by the operation described above.
  ```

- **Returns:**

  ```text
  Values returned by ``build_fvg_zones_for_plot``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_ltf_plot_zone_starts_two_candles_before_confirmation`](../../../../tests/unit/features/test_po3_config.py#L930)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        open_[15:20] = 112.0
        bars = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close},
            index=idx,
        )
        zones = build_fvg_zones_for_plot(bars, htf="M15", ltf="M5")
        bull = [z for z in zones if z.kind == "ltf_ifvg" and z.side == "bullish"]
        assert bull, "expected an LTF bullish IFVG"
        assert bull[0].start_ts == pd.Timestamp("2025-01-02 10:05", tz="Etc/GMT-3")
```

2. [test fixture: `test_plot_zone_starts_at_bar2_open`](../../../../tests/unit/features/test_po3_config.py#L937)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_plot_zone_starts_at_bar2_open(self) -> None:
    bars = self._m15_bullish_gap_m1()
    zones = build_fvg_zones_for_plot(bars, htf="M15", ltf="M5")
    bull = [z for z in zones if z.kind == "htf_fvg" and z.side == "bullish"]
    assert bull, "expected at least one HTF bullish plot zone"
    z = bull[0]
    assert z.start_ts == pd.Timestamp("2025-01-02 16:15", tz="Etc/GMT-3")
    assert z.zone_low == pytest.approx(100.0)
    assert z.zone_high == pytest.approx(110.0)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/features/index`
