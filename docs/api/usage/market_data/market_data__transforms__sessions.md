# Market data · `transforms.sessions`

This page contains 3 public callable records owned by `market_data.transforms.sessions`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `add_session_id`

**Kind:** function · **Status:** stable · **Owner:** `market_data.transforms.sessions`

**Purpose:** Add a ``session_id`` integer column: unique per calendar date.

**Exact API:** {py:obj}`market_data.transforms.sessions.add_session_id` · **Source:** [market_data/transforms/sessions.py:162](../../../../market_data/transforms/sessions.py#L162)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``add_session_id``.
  ```

**Observed usage:**

1. [test fixture: `test_session_id_increments_per_day`](../../../../tests/unit/features/test_session_filter.py#L51)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_session_id_increments_per_day():
    idx = pd.date_range("2025-01-06 16:30", periods=60, freq="1min", tz="Etc/GMT-3")
    idx2 = pd.date_range("2025-01-07 16:30", periods=60, freq="1min", tz="Etc/GMT-3")
    combined = idx.append(idx2)
    df = pd.DataFrame({"close": 1.0}, index=combined)
    df = add_session_id(df)
    sessions = df["session_id"].unique()
    assert len(sessions) == 2
    assert sessions[0] != sessions[1]
```

2. [test fixture: `_ohlc_index`](../../../../tests/unit/simulation/test_environment/test_ny_steps_eod.py#L34)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        },
        index=idx,
    )
    bars.index.name = "datetime"
    bars = add_session_labels(bars)
    bars = add_session_id(bars)
    return bars
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `add_session_labels`

**Kind:** function · **Status:** stable · **Owner:** `market_data.transforms.sessions`

**Purpose:** Add a ``session`` column (asia/london/ny/closed) using :func:`get_session`.

**Exact API:** {py:obj}`market_data.transforms.sessions.add_session_labels` · **Source:** [market_data/transforms/sessions.py:104](../../../../market_data/transforms/sessions.py#L104)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  tz: Text or path value identifying the tz.
  ny_end: Text or path value identifying the ny end.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``add_session_labels``.
  ```

**Observed usage:**

1. [test fixture: `test_asia_masks_london_and_asia_ctx`](../../../../tests/unit/features/test_pd_context.py#L80)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def test_asia_masks_london_and_asia_ctx(self, bars: pd.DataFrame) -> None:
        atr = pd.Series(1.0, index=bars.index)
        ctx = build_pd_context_features(bars, atr)
        asia = add_session_labels(bars)["session"] == "asia"
        assert asia.any()
        assert (ctx.loc[asia, "ctx_asia_active"] == 0.0).all()
        assert (ctx.loc[asia, "ctx_london_active"] == 0.0).all()
        assert (ctx.loc[asia, "ctx_asia_high"] == 0.0).all()
        assert (ctx.loc[asia, "ctx_london_high"] == 0.0).all()
# … caller assertions omitted …
```

2. [test fixture: `test_london_has_asia_not_completed_self_as_running`](../../../../tests/unit/features/test_pd_context.py#L96)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    def test_london_has_asia_not_completed_self_as_running(self, bars: pd.DataFrame) -> None:
        atr = pd.Series(1.0, index=bars.index)
        ctx = build_pd_context_features(bars, atr)
        london = add_session_labels(bars)["session"] == "london"
        assert london.any()
        assert (ctx.loc[london, "ctx_asia_active"] == 1.0).all()
        assert (ctx.loc[london, "ctx_london_active"] == 1.0).all()
        # Completed Asia for day 1 should equal planted asia extreme 105.
        d1_lon = london & (_index_dates(bars.index) == pd.Timestamp("2025-01-06").date())
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `ny_session_mask`

**Kind:** function · **Status:** stable · **Owner:** `market_data.transforms.sessions`

**Purpose:** Boolean mask of bars whose clock time falls in the tradable NY window.

**Exact API:** {py:obj}`market_data.transforms.sessions.ny_session_mask` · **Source:** [market_data/transforms/sessions.py:83](../../../../market_data/transforms/sessions.py#L83)

**Inputs and outputs:**

- **Args:**

  ```text
  index: Position or label identifying the requested item.
  start: Text or path value identifying the start.
  end: Text or path value identifying the end.
  ```

- **Returns:**

  ```text
  Result of boolean mask of bars whose clock time falls in the tradable NY window.
  ```

**Observed usage:**

1. [test fixture: `test_trading_mask_separate_from_features`](../../../../tests/unit/features/test_session_filter.py#L59)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_trading_mask_separate_from_features(sample_bars):
    labeled = add_session_labels(sample_bars)
    mask = ny_session_mask(pd.DatetimeIndex(labeled.index))
    assert len(labeled) == len(sample_bars)
    assert mask.sum() < len(labeled)
    assert labeled.loc[mask, "session"].eq("ny").all()
```

2. [production caller: `plot_coverage_calendar`](../../../../evaluation/plotting/data_plots.py#L82)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
    _apply_style()
    idx = pd.DatetimeIndex(bars.index)
    days = idx.normalize()
    full = days.value_counts().sort_index()
    ny_mask = ny_session_mask(idx)
    ny_counts = (
        days[ny_mask.to_numpy()].value_counts().sort_index().reindex(full.index).fillna(0)
        if ny_mask.any()
        else pd.Series(0.0, index=full.index)
    )
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
