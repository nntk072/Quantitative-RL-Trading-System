# Market data · `news.guard`

This page contains 5 public callable records owned by `market_data.news.guard`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `NewsGuardConfig`

**Kind:** class · **Status:** stable · **Owner:** `market_data.news.guard`

**Purpose:** Settings for the news and spike guard, from ``execution.news_spike_guard``.

**Exact API:** {py:obj}`market_data.news.guard.NewsGuardConfig` · **Source:** [market_data/news/guard.py:36](../../../../market_data/news/guard.py#L36)

**Observed usage:**

1. [test fixture: `test_event_backtest_cancels_resting_limit_when_release_blackout_starts`](../../../../tests/integration/backtest/test_agent_selected_entry_execution.py#L2013)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        f"{release_bar.strftime('%Y-%m-%dT%H:%M:%SZ')},CPI,CPI,x,y,z\n",
        encoding="utf-8",
    )
    # Zero-minute blackout: only the release bar is blocked. The spike multiple is huge so
    # the spike rule cannot fire.
    guard = NewsGuardConfig(
        calendar_path=calendar,
        blackout_minutes_before=0,
        blackout_minutes_after=0,
        spike_atr_multiple=1e9,
        exempt_open_manipulation=False,
        baseline_lookback_sessions=5,
    )
    # A tick far above the limit, after the release, so the order cannot fill on its own.
    tick_time = bars.index[5] + pd.Timedelta(seconds=30)
    tickbook = TickBook(
        np.asarray([tick_time.value], dtype=np.int64),
        np.asarray([20_100.0]),
# … caller assertions omitted …
```

2. [test fixture: `_run`](../../../../tests/integration/backtest/test_news_spike_guard_backtest.py#L52)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        "utc_time,category,summary,source,source_sha256,retrieved_on\n"
        f"{index[10].strftime('%Y-%m-%dT%H:%M:%SZ')},CPI,CPI,x,y,z\n",
        encoding="utf-8",
    )
    guard = (
        NewsGuardConfig(
            calendar_path=calendar,
            exempt_open_manipulation=False,
            baseline_lookback_sessions=5,
        )
        if guard_on
        else None
    )
    result = run_backtest(
        bars,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `causal_atr5`

**Kind:** function · **Status:** stable · **Owner:** `market_data.news.guard`

**Purpose:** 5-bar average true range from past bars only (used when no ``atr_5`` feature exists).

**Exact API:** {py:obj}`market_data.news.guard.causal_atr5` · **Source:** [market_data/news/guard.py:239](../../../../market_data/news/guard.py#L239)

**Inputs and outputs:**

- **Args:**

  ```text
  high: High price per bar.
  low: Low price per bar.
  close: Close price per bar.
  ```

- **Returns:**

  ```text
  Rolling 5-bar mean of true range, one value per bar.
  ```

**Observed usage:**

1. [production caller: `run_backtest`](../../../../simulation/backtest/event_driven_backtest.py#L1138)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            list(pd.DatetimeIndex(bars.index).to_pydatetime()),
            bars["close"].to_numpy(dtype=float),
            (
                features["atr_5"].to_numpy(dtype=float)
                if "atr_5" in features.columns
                else causal_atr5(bars["high"], bars["low"], bars["close"])
            ),
            (
                bars["session_id"].to_numpy(dtype=np.int64)
                if "session_id" in bars.columns
                else np.zeros(len(bars), dtype=np.int64)
# … caller assertions omitted …
```

2. [production caller: `_initialize_observation_arrays`](../../../../simulation/environment/observation_arrays_initialization.py#L296)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            )
            self._news_close = bars["close"].to_numpy(dtype=float)
            self._news_atr = (
                features["atr_5"].to_numpy(dtype=float)
                if "atr_5" in features.columns
                else causal_atr5(bars["high"], bars["low"], bars["close"])
            )
            self._news_labels = (
                bars["session"].to_numpy().astype(str)
                if "session" in bars.columns
                else np.full(len(bars), "all")
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `load_release_times`

**Kind:** function · **Status:** stable · **Owner:** `market_data.news.guard`

**Purpose:** Release times (UTC) from a calendar CSV written by ``market_data.news.calendar``.

**Exact API:** {py:obj}`market_data.news.guard.load_release_times` · **Source:** [market_data/news/guard.py:48](../../../../market_data/news/guard.py#L48)

**Inputs and outputs:**

- **Args:**

  ```text
  calendar_path: Calendar CSV path.
  ```

- **Returns:**

  ```text
  Release times as timezone-aware UTC datetimes.
  ```

**Observed usage:**

1. [test fixture: `test_load_release_times_reads_utc_column`](../../../../tests/unit/market_data/test_news_guard.py#L262)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_load_release_times_reads_utc_column(tmp_path: Path) -> None:
    path = tmp_path / "calendar.csv"
    path.write_text(
        "utc_time,category,summary,source,source_sha256,retrieved_on\n"
        "2025-02-07T13:30:00Z,NFP,Employment Situation,x,y,2026-11-23\n",
        encoding="utf-8",
    )

    assert load_release_times(path) == [datetime(2025, 2, 7, 13, 30, tzinfo=UTC)]
```

2. [production caller: `run_backtest`](../../../../simulation/backtest/event_driven_backtest.py#L1150)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            (
                bars["session"].to_numpy().astype(str)
                if "session" in bars.columns
                else np.full(len(bars), "all")
            ),
            load_release_times(news_guard.calendar_path),
            news_guard,
            open_manipulation_bars=settings.open_manipulation_bars,
        )
    )
    bar_duration = _bar_duration(bar_times)
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `news_block_mask`

**Kind:** function · **Status:** stable · **Owner:** `market_data.news.guard`

**Purpose:** Boolean mask over bars: True where new entries are blocked.

**Exact API:** {py:obj}`market_data.news.guard.news_block_mask` · **Source:** [market_data/news/guard.py:103](../../../../market_data/news/guard.py#L103)

**Inputs and outputs:**

- **Args:**

  ```text
  bar_times: Bar start times.
  close: Close price per bar.
  atr: ATR per bar, used as the spike baseline source.
  session_ids: Session identifier per bar.
  session_labels: Session label per bar.
  release_times: Scheduled release times (UTC).
  config: Guard settings.
  open_manipulation_bars: Number of bars at the start of each NY session that are exempt
      from the spike rule when ``config.exempt_open_manipulation`` is set.
  ```

- **Returns:**

  ```text
  Boolean mask, True where new entries are blocked.
  ```

**Observed usage:**

1. [test fixture: `test_spike_blocks_new_entries_outside_ny_open_window`](../../../../tests/unit/market_data/test_news_guard.py#L64)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    times, ids, labels = _sessions(2, 6)
    atr = np.full(12, 1.0)
    close = np.full(12, 100.0)
    close[10] = 105.0  # a 5-point move in bar 10 of session 1, versus a 1.0 baseline

    mask = news_block_mask(
        times,
        close,
        atr,
        ids,
        labels,
        release_times=[],
        config=_config(),
        open_manipulation_bars=0,
    )

    assert mask[10]
    assert not mask[0:6].any()
```

2. [test fixture: `test_ny_open_manipulation_is_not_treated_as_news`](../../../../tests/unit/market_data/test_news_guard.py#L85)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    times, ids, labels = _sessions(2, 6, label="ny")
    atr = np.full(12, 1.0)
    close = np.full(12, 100.0)
    close[10] = 105.0

    mask = news_block_mask(
        times,
        close,
        atr,
        ids,
        labels,
        release_times=[],
        config=_config(),
        open_manipulation_bars=3,
    )

    # Bar 10 is at offset 4 of its NY session, outside the 3-bar open window, so it blocks.
    assert mask[10]
    exempt = news_block_mask(
        times,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `news_guard_config`

**Kind:** function · **Status:** stable · **Owner:** `market_data.news.guard`

**Purpose:** Build the guard from ``execution.news_spike_guard``; None when the guard is disabled.

**Exact API:** {py:obj}`market_data.news.guard.news_guard_config` · **Source:** [market_data/news/guard.py:214](../../../../market_data/news/guard.py#L214)

**Inputs and outputs:**

- **Args:**

  ```text
  block: The ``execution.news_spike_guard`` config mapping, or None.
  ```

- **Returns:**

  ```text
  The guard settings, or None when the guard is disabled or absent.
  ```

**Observed usage:**

1. [test fixture: `test_news_guard_config_is_optional_and_resolves_relative_calendar_path`](../../../../tests/unit/market_data/test_news_guard.py#L266)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_news_guard_config_is_optional_and_resolves_relative_calendar_path() -> None:
    assert news_guard_config(None) is None
    assert news_guard_config({"enabled": False}) is None

    config = news_guard_config(
        {
            "enabled": True,
# … caller assertions omitted …
```

2. [production caller: `make_env`](../../../../simulation/environment/trading_environment_factory.py#L684)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        tickbook=configured_tickbook,
        tick_execution_required=tick_execution_required(cfg),
        fill_delay_ms=fill_delay_ms(cfg),
        randomized_fill_latency_ms=randomized_fill_latency_ms(cfg),
        max_tick_quote_wait_ms=max_tick_quote_wait_ms(cfg),
        news_guard=news_guard_config(cfg.execution.get("news_spike_guard")),
        server_side_protective_orders=bool(
            cfg.execution.get("server_side_protective_orders", False)
        ),
        tick_fill_slippage_points=cost_model(cfg).slippage_points,
        use_vae=use_vae,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
