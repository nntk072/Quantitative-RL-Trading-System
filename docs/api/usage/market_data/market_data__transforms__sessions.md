# Market data · `transforms.sessions`

This page contains 3 public callable records owned by `market_data.transforms.sessions`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `add_session_id`

**Kind:** function · **Status:** stable · **Owner:** `market_data.transforms.sessions`

**Purpose:** Add a ``session_id`` integer column: unique per calendar date.

**Exact API:** {py:obj}`market_data.transforms.sessions.add_session_id` · **Source:** [market_data/transforms/sessions.py:243](../../../../market_data/transforms/sessions.py#L243)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  session_tz: Timezone used to derive each row's calendar-session date.
  source_clock_model: Interpretation of source-index wall labels.
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

**Exact API:** {py:obj}`market_data.transforms.sessions.add_session_labels` · **Source:** [market_data/transforms/sessions.py:179](../../../../market_data/transforms/sessions.py#L179)

**Inputs and outputs:**

- **Args:**

  ```text
  df: Input DataFrame supplying the rows used by this calculation.
  tz: Session timezone.
  ny_end: Inclusive NY-session end.
  source_clock_model: Interpretation of source-index wall labels.
  ```

- **Returns:**

  ```text
  DataFrame returned by ``add_session_labels``.
  ```

**Observed usage:**

1. [test fixture: `test_asia_masks_london_and_asia_ctx`](../../../../tests/unit/features/test_pd_context.py#L97)

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

2. [test fixture: `test_london_has_asia_not_completed_self_as_running`](../../../../tests/unit/features/test_pd_context.py#L113)

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

**Exact API:** {py:obj}`market_data.transforms.sessions.ny_session_mask` · **Source:** [market_data/transforms/sessions.py:136](../../../../market_data/transforms/sessions.py#L136)

**Inputs and outputs:**

- **Args:**

  ```text
  index: Position or label identifying the requested item.
  start: Session start as HH:MM. Defaults to the selected exchange clock.
  end: Session end as HH:MM. Defaults to the selected exchange clock.
  session_tz: IANA timezone for boundaries; ``None`` preserves legacy behavior.
  source_clock_model: Interpretation of source-index wall labels.
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

2. [test fixture: `test_ny_mask_converts_helsinki_wall_time_before_classifying`](../../../../tests/unit/market_data/test_helsinki_ny_sessions.py#L36)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_ny_mask_converts_helsinki_wall_time_before_classifying(
    date: str, labels: list[str], expected: list[bool]
) -> None:
    index = pd.DatetimeIndex([f"{date} {label}" for label in labels]).tz_localize("Etc/GMT-3")

    actual = ny_session_mask(
        index,
        start="09:30",
        end="16:00",
        session_tz="America/New_York",
        source_clock_model="europe_helsinki",
    )

    assert actual.tolist() == expected
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
