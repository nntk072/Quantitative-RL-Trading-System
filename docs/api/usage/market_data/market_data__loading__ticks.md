# Market data · `loading.ticks`

This page contains 16 public callable records owned by `market_data.loading.ticks`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TickBook`

**Kind:** class · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Sorted bid/ask lookup table backed by NumPy arrays.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook` · **Source:** [market_data/loading/ticks.py:632](../../../../market_data/loading/ticks.py#L632)

**Observed usage:**

1. [test fixture: `test_environment_and_backtest_match_on_one_shared_tick_execution_trace`](../../../../tests/integration/backtest/test_account_transition_parity.py#L458)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            (index[2] + pd.Timedelta(milliseconds=100)).value,
            (index[3] + pd.Timedelta(milliseconds=100)).value,
        ],
        dtype=np.int64,
    )
    tickbook = TickBook(
        tick_times,
        np.asarray([100.0, 99.5]),
        np.asarray([100.2, 99.7]),
    )
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=2.0)
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
# … caller assertions omitted …
```

2. [test fixture: `test_environment_and_backtest_consume_actions_while_delayed_entry_is_pending`](../../../../tests/integration/backtest/test_account_transition_parity.py#L598)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "last_swing_low": np.full(len(index), 90.0),
            "last_swing_high": np.full(len(index), 110.0),
        },
        index=index,
    )
    tickbook = TickBook(
        np.asarray(
            [index[i].value for i in (5, 8, 9)] + [(index[-1] + pd.Timedelta(minutes=1)).value],
            dtype=np.int64,
        ),
        np.asarray([100.0, 99.5, 99.2, 99.0]),
        np.asarray([100.2, 99.7, 99.4, 99.2]),
    )
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    # Environment action IDs 1 and 10 encode long and short; the backtest
    # adapter below receives their signed directions directly.
    actions = [1, 0, 0, 0, 10, 10, 19, 0, 0, 0, 0]
    env = TradingEnv(
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook`

**Kind:** class · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Sorted bid/ask lookup table backed by NumPy arrays.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook` · **Source:** [market_data/loading/ticks.py:632](../../../../market_data/loading/ticks.py#L632)

**Observed usage:**

1. [test fixture: `test_environment_and_backtest_match_on_one_shared_tick_execution_trace`](../../../../tests/integration/backtest/test_account_transition_parity.py#L458)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            (index[2] + pd.Timedelta(milliseconds=100)).value,
            (index[3] + pd.Timedelta(milliseconds=100)).value,
        ],
        dtype=np.int64,
    )
    tickbook = TickBook(
        tick_times,
        np.asarray([100.0, 99.5]),
        np.asarray([100.2, 99.7]),
    )
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=2.0)
    env = TradingEnv(
        bars,
        features,
        obs_window=1,
# … caller assertions omitted …
```

2. [test fixture: `test_environment_and_backtest_consume_actions_while_delayed_entry_is_pending`](../../../../tests/integration/backtest/test_account_transition_parity.py#L598)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            "last_swing_low": np.full(len(index), 90.0),
            "last_swing_high": np.full(len(index), 110.0),
        },
        index=index,
    )
    tickbook = TickBook(
        np.asarray(
            [index[i].value for i in (5, 8, 9)] + [(index[-1] + pd.Timedelta(minutes=1)).value],
            dtype=np.int64,
        ),
        np.asarray([100.0, 99.5, 99.2, 99.0]),
        np.asarray([100.2, 99.7, 99.4, 99.2]),
    )
    cost_model = CostModel(spread_points=0.0, point_size=0.01, commission_per_lot=0.0)
    # Environment action IDs 1 and 10 encode long and short; the backtest
    # adapter below receives their signed directions directly.
    actions = [1, 0, 0, 0, 10, 10, 19, 0, 0, 0, 0]
    env = TradingEnv(
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `build_tick_book`

**Kind:** function · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Load an MT5 tick CSV, optionally session-filter, forward-fill, build a TickBook.

**Exact API:** {py:obj}`market_data.loading.ticks.build_tick_book` · **Source:** [market_data/loading/ticks.py:1140](../../../../market_data/loading/ticks.py#L1140)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input file or directory.
  tz: Text or path value identifying the tz.
  source_clock_model: Optional interpretation of source wall-clock labels.
  session_start: Session start used by the operation described above.
  session_end: Session end used by the operation described above.
  cache_path: Path or filename identifying the cache.
  force: Whether to enable or require the force.
  chunksize: Numeric value used for the chunksize.
  price_grid_increment: Price grid increment used by the operation described above.
  diagnostics: Optional mutable counter record populated during a raw-source build.
  start_inclusive: Optional first local calendar date to include.
  end_exclusive: Optional exclusive local timestamp bound.
  end_date_inclusive: Optional last local calendar date represented by the cache.
  end_inclusive: Optional last local calendar date to include; bypasses full-source caches.
  ```

- **Returns:**

  ```text
  Result of load an MT5 tick CSV, optionally session-filter, forward-fill, build a TickBook.
  ```

**Observed usage:**

1. [test fixture: `test_equal_timestamp_quote_uses_first_source_row_across_chunks`](../../../../tests/unit/market_data/test_ticks.py#L140)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            ("2025.01.06", "16:30:00.000", 100.0, 100.6),
            ("2025.01.06", "16:30:00.000", 100.2, 100.8),
            ("2025.01.06", "16:30:01.000", 101.0, 101.6),
        ],
    )
    book = build_tick_book(csv_path, session_start=None, session_end=None, chunksize=1)
    tick_time = pd.Timestamp("2025-01-06 16:30:00", tz="Etc/GMT-3")

    event = book.quote_event_at(tick_time)
    fill = resolve_tick_execution(
        book,
# … caller assertions omitted …
```

2. [test fixture: `test_build_tick_book_quantizes_executable_bid_ask`](../../../../tests/unit/market_data/test_ticks.py#L795)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    _write_tick_csv(
        csv_path,
        [("2025.01.06", "16:30:00.000", 25633.68, 25633.99)],
    )

    book = build_tick_book(
        csv_path,
        session_start=None,
        session_end=None,
        chunksize=1,
        price_grid_increment=0.25,
    )

    quote = book.quote_at(pd.Timestamp("2025-01-06 16:30:00", tz="Etc/GMT-3"))
    assert quote == pytest.approx((25633.75, 25634.0))
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.bar_arrays`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return the quote arrays for the same half-open bar interval as ``bar_quote_ns``.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.bar_arrays` · **Source:** [market_data/loading/ticks.py:874](../../../../market_data/loading/ticks.py#L874)

**Inputs and outputs:**

- **Args:**

  ```text
  bar_start: Bar start used by the operation described above.
  bar_minutes: Numeric value used for the bar minutes.
  ```

- **Returns:**

  ```text
  Quote nanoseconds (UTC), bid and ask arrays, in timestamp order.
  ```

**Observed usage:**

1. [test fixture: `test_tickbook_interval_helpers_use_half_open_bar_windows`](../../../../tests/unit/market_data/test_ticks.py#L1898)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        np.asarray([end.value], dtype=np.int64), np.asarray([101.0]), np.asarray([101.5])
    )
    assert not boundary_only.has_ticks_between(start, end)
    assert boundary_only.has_ticks_between(end, end + pd.Timedelta(minutes=1))
    assert list(book.bar_quote_ns(start)) == [(inside.value, 100.0, 100.5)]
    timestamps, bid, ask = book.bar_arrays(start)
    np.testing.assert_array_equal(timestamps, [inside.value])
    np.testing.assert_array_equal(bid, [100.0])
    np.testing.assert_array_equal(ask, [100.5])
    empty = TickBook(np.array([], dtype=np.int64), np.array([]), np.array([]))
    assert not empty.has_ticks_between(start, end)
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.bar_quote_ns`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Yield (UTC ns, bid, ask) for the same quotes as ``bar_quotes``, without Timestamps.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.bar_quote_ns` · **Source:** [market_data/loading/ticks.py:855](../../../../market_data/loading/ticks.py#L855)

**Inputs and outputs:**

- **Args:**

  ```text
  bar_start: Bar start used by the operation described above.
  bar_minutes: Numeric value used for the bar minutes.
  ```

- **Yields:**

  ```text
  Quote nanoseconds (UTC), bid and ask, in the same order as ``bar_quotes``.
  ```

**Observed usage:**

1. [test fixture: `test_tickbook_interval_helpers_use_half_open_bar_windows`](../../../../tests/unit/market_data/test_ticks.py#L1897)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    boundary_only = TickBook(
        np.asarray([end.value], dtype=np.int64), np.asarray([101.0]), np.asarray([101.5])
    )
    assert not boundary_only.has_ticks_between(start, end)
    assert boundary_only.has_ticks_between(end, end + pd.Timedelta(minutes=1))
    assert list(book.bar_quote_ns(start)) == [(inside.value, 100.0, 100.5)]
    timestamps, bid, ask = book.bar_arrays(start)
    np.testing.assert_array_equal(timestamps, [inside.value])
    np.testing.assert_array_equal(bid, [100.0])
    np.testing.assert_array_equal(ask, [100.5])
    empty = TickBook(np.array([], dtype=np.int64), np.array([]), np.array([]))
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.bar_quotes`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Yield recorded quotes in timestamp order within a half-open bar interval.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.bar_quotes` · **Source:** [market_data/loading/ticks.py:892](../../../../market_data/loading/ticks.py#L892)

**Inputs and outputs:**

- **Args:**

  ```text
  bar_start: Bar start used by the operation described above.
  bar_minutes: Numeric value used for the bar minutes.
  ```

- **Yields:**

  ```text
  Each bar quotes value, yielded in processing order.
  ```

**Observed usage:**

1. [test fixture: `test_build_tick_book_filters_nonfinite_nonpositive_and_crossed_quotes`](../../../../tests/unit/market_data/test_ticks.py#L1643)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            ("2025.01.06", "16:30:06.000", np.nan, 104.5),
        ],
    )

    book = build_tick_book(csv_path, tz="Etc/GMT-3", chunksize=3)
    quotes = list(book.bar_quotes(pd.Timestamp("2025-01-06 16:30:00", tz="Etc/GMT-3")))

    assert len(quotes) == 5
    assert all(np.isfinite(bid) and np.isfinite(ask) and 0 < bid <= ask for _, bid, ask in quotes)
    assert quotes[1][1:] == pytest.approx((100.0, 101.2))
    assert quotes[-1][1:] == pytest.approx((104.0, 104.5))
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.content_sha256`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Fingerprint the ordered timestamp and quote arrays used for execution.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.content_sha256` · **Source:** [market_data/loading/ticks.py:797](../../../../market_data/loading/ticks.py#L797)

**Inputs and outputs:**

- **Returns:**

  ```text
  SHA-256 fingerprint of ordered timestamps, bids, and asks.
  ```

**Observed usage:**

1. [test fixture: `test_ticks_covering_interprets_helsinki_source_clock_for_dst`](../../../../tests/unit/market_data/test_ticks.py#L89)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    bars = pd.DataFrame({"close": [100.0]}, index=pd.DatetimeIndex([bar_time]))

    sliced = ticks_covering(book, bars, source_clock_model="europe_helsinki")

    assert sliced is not None
    assert sliced.content_sha256() == book.content_sha256()
```

2. [test fixture: `test_tickbook_content_hash_includes_stable_quote_order`](../../../../tests/unit/market_data/test_ticks.py#L98)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_tickbook_content_hash_includes_stable_quote_order() -> None:
    book = _make_book()
    identical = TickBook(book._ts.copy(), book._bid.copy(), book._ask.copy())
    reordered = TickBook(book._ts[::-1].copy(), book._bid[::-1].copy(), book._ask[::-1].copy())
    repriced = TickBook(book._ts.copy(), book._bid + 0.01, book._ask.copy())

    assert book.content_sha256() == identical.content_sha256()
    assert book.content_sha256() != reordered.content_sha256()
    assert book.content_sha256() != repriced.content_sha256()
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.delayed_exit_event`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return trigger kind, actual fill time, and delayed executable quote.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.delayed_exit_event` · **Source:** [market_data/loading/ticks.py:951](../../../../market_data/loading/ticks.py#L951)

**Inputs and outputs:**

- **Args:**

  ```text
  bar_start: Bar start used by the operation described above.
  direction: Signed trade direction: 1 for long and -1 for short.
  sl: Sl used by the operation described above.
  tp: Tp used by the operation described above.
  delay: Delay used by the operation described above.
  bar_minutes: Numeric value used for the bar minutes.
  earliest_time: Earliest time used by the operation described above.
  ```

- **Returns:**

  ```text
  Values returned by ``delayed_exit_event``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_delayed_exit_uses_trigger_then_delayed_observed_quote`](../../../../tests/unit/market_data/test_ticks.py#L1917)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        np.array([trigger.value, fill_quote.value], dtype=np.int64),
        np.array([94.0, 93.5]),
        np.array([94.5, 94.0]),
    )

    event = book.delayed_exit_event(
        start, direction=1, sl=95.0, tp=None, delay=pd.Timedelta(seconds=2)
    )

    assert event == ("sl", fill_quote, 93.5, 94.0)
    assert book.delayed_exit_quote(
        start, direction=1, sl=95.0, tp=None, delay=pd.Timedelta(seconds=2)
    ) == ("sl", 93.5, 94.0)
# … caller assertions omitted …
```

2. [test fixture: `test_delayed_exit_selects_take_profit_trigger_when_no_stop_precedes_it`](../../../../tests/unit/market_data/test_ticks.py#L1953)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        np.array([(start + pd.Timedelta(seconds=1)).value, trigger.value], dtype=np.int64),
        np.array([100.0, 106.0]),
        np.array([100.5, 106.5]),
    )

    event = book.delayed_exit_event(
        start,
        direction=1,
        sl=95.0,
        tp=105.0,
        delay=pd.Timedelta(0),
    )

    assert event == ("tp", trigger, 106.0, 106.5)
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.delayed_exit_quote`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Quote ``delay`` after the first tick that trades through SL or TP.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.delayed_exit_quote` · **Source:** [market_data/loading/ticks.py:915](../../../../market_data/loading/ticks.py#L915)

**Inputs and outputs:**

- **Args:**

  ```text
  bar_start: Bar start used by the operation described above.
  direction: Signed trade direction: 1 for long and -1 for short.
  sl: Sl used by the operation described above.
  tp: Tp used by the operation described above.
  delay: Delay used by the operation described above.
  bar_minutes: Numeric value used for the bar minutes.
  ```

- **Returns:**

  ```text
  Values returned by ``delayed_exit_quote``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_delayed_exit_uses_trigger_then_delayed_observed_quote`](../../../../tests/unit/market_data/test_ticks.py#L1922)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    event = book.delayed_exit_event(
        start, direction=1, sl=95.0, tp=None, delay=pd.Timedelta(seconds=2)
    )

    assert event == ("sl", fill_quote, 93.5, 94.0)
    assert book.delayed_exit_quote(
        start, direction=1, sl=95.0, tp=None, delay=pd.Timedelta(seconds=2)
    ) == ("sl", 93.5, 94.0)
    assert (
        book.delayed_exit_event(start, direction=1, sl=None, tp=None, delay=pd.Timedelta(seconds=2))
        is None
    )
    assert book.execution_quote_event_at(fill_quote + pd.Timedelta(seconds=1)) is None
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.execution_quote_event_at`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return the first quote at or after an execution arrival time.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.execution_quote_event_at` · **Source:** [market_data/loading/ticks.py:706](../../../../market_data/loading/ticks.py#L706)

**Inputs and outputs:**

- **Args:**

  ```text
  ts: Ts used by the operation described above.
  ```

- **Returns:**

  ```text
  Values returned by ``execution_quote_event_at``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_environment_and_backtest_match_on_one_shared_tick_execution_trace`](../../../../tests/integration/backtest/test_account_transition_parity.py#L562)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        assert env_event["price"] == pytest.approx(backtest_event["price"])
        assert pd.Timestamp(env_event["actual_tick_time"]) == pd.Timestamp(
            backtest_event["actual_tick_time"]
        )

    exit_quote = tickbook.execution_quote_event_at(index[3])
    assert exit_quote is not None
    assert env_close["fill_time"] == exit_quote[0]
    assert env_close["pnl"] == pytest.approx(backtest_close["pnl"])
    assert env.account.balance == pytest.approx(result["account"].balance)
    lots = float(env_open["lots"])
# … caller assertions omitted …
```

2. [test fixture: `test_delayed_exit_uses_trigger_then_delayed_observed_quote`](../../../../tests/unit/market_data/test_ticks.py#L1929)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    ) == ("sl", 93.5, 94.0)
    assert (
        book.delayed_exit_event(start, direction=1, sl=None, tp=None, delay=pd.Timedelta(seconds=2))
        is None
    )
    assert book.execution_quote_event_at(fill_quote + pd.Timedelta(seconds=1)) is None
    assert (
        book.delayed_exit_event(start, direction=1, sl=95.0, tp=None, delay=pd.Timedelta(hours=1))
        is None
    )
    assert (
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.first_limit_execution_event`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return the earliest source-ordered quote that crosses a limit.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.first_limit_execution_event` · **Source:** [market_data/loading/ticks.py:733](../../../../market_data/loading/ticks.py#L733)

**Inputs and outputs:**

- **Args:**

  ```text
  direction: Limit-order side, ``1`` for buy or ``-1`` for sell.
  limit_price: Submitted limit price.
  start_time: Earliest timestamp eligible for a fill.
  expiry_time: Last timestamp eligible for a fill, inclusive.
  require_trade_through: Whether a quote must cross beyond the limit.
  ```

- **Returns:**

  ```text
  Earliest matching timestamp and its bid/ask, or ``None`` if unfilled.
  ```

**Observed usage:**

1. [test fixture: `test_first_limit_execution_event_rejects_invalid_side_price_and_time_order`](../../../../tests/unit/market_data/test_ticks.py#L2038)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_first_limit_execution_event_rejects_invalid_side_price_and_time_order() -> None:
    book = _make_book()
    start = pd.Timestamp("2025-01-06 16:30:00", tz="UTC")

    with pytest.raises(ValueError, match=r"direction must be -1 or \+1"):
        book.first_limit_execution_event(0, 100.0, start, start)
    with pytest.raises(ValueError, match="finite and positive"):
        book.first_limit_execution_event(1, float("inf"), start, start)
    with pytest.raises(ValueError, match="timezone-aware"):
        book.first_limit_execution_event(1, 100.0, pd.Timestamp("2025-01-06 16:30:00"), start)
    with pytest.raises(ValueError, match="cannot precede"):
        book.first_limit_execution_event(1, 100.0, start, start - pd.Timedelta(seconds=1))
```

2. [test fixture: `test_first_limit_execution_event_uses_inclusive_expiry_and_trade_through`](../../../../tests/unit/market_data/test_ticks.py#L2052)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_first_limit_execution_event_uses_inclusive_expiry_and_trade_through() -> None:
    book = _make_book()
    start = pd.Timestamp("2025-01-06 16:30:10", tz="UTC")
    expiry = start

    assert book.first_limit_execution_event(1, 101.6, start, expiry) == (
        expiry,
        101.0,
        101.6,
    )
    assert (
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.has_ticks_between`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return whether any quote falls in the half-open interval [start, end).

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.has_ticks_between` · **Source:** [market_data/loading/ticks.py:817](../../../../market_data/loading/ticks.py#L817)

**Inputs and outputs:**

- **Args:**

  ```text
  start: Start used by the operation described above.
  end: End used by the operation described above.
  ```

- **Returns:**

  ```text
  Whether has ticks between meets the requested condition.
  ```

**Observed usage:**

1. [test fixture: `test_tickbook_interval_helpers_use_half_open_bar_windows`](../../../../tests/unit/market_data/test_ticks.py#L1891)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        np.array([inside.value, end.value], dtype=np.int64),
        np.array([100.0, 101.0]),
        np.array([100.5, 101.5]),
    )

    assert book.has_ticks_between(start, end)
    boundary_only = TickBook(
        np.asarray([end.value], dtype=np.int64), np.asarray([101.0]), np.asarray([101.5])
    )
    assert not boundary_only.has_ticks_between(start, end)
    assert boundary_only.has_ticks_between(end, end + pd.Timedelta(minutes=1))
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.last_bar_quote_ns`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return the final source-ordered quote in a half-open bar interval.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.last_bar_quote_ns` · **Source:** [market_data/loading/ticks.py:834](../../../../market_data/loading/ticks.py#L834)

**Inputs and outputs:**

- **Args:**

  ```text
  bar_start: Start of the bar interval.
  bar_minutes: Length of the interval in minutes.
  ```

- **Returns:**

  ```text
  The final quote as ``(UTC nanoseconds, bid, ask)``, or ``None`` when
  the interval contains no ticks.
  ```

**Observed usage:**

1. [test fixture: `test_last_bar_quote_lookup_preserves_half_open_bar_and_source_order`](../../../../tests/unit/simulation/test_environment/test_candidate_geometry_observation.py#L174)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        np.asarray([start_ns - 1, start_ns, start_ns + 30, start_ns + 30, end_ns]),
        np.asarray([98.0, 99.0, 99.8, 99.9, 101.0]),
        np.asarray([98.1, 99.1, 99.9, 100.0, 101.1]),
    )

    assert tickbook.last_bar_quote_ns(bar_start, bar_minutes=1) == (
        start_ns + 30,
        99.9,
        100.0,
    )
    empty_tickbook = TickBook(np.asarray([], dtype=np.int64), np.asarray([]), np.asarray([]))
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.quote_at`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return ``(bid, ask)`` for the first tick at or after *ts*.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.quote_at` · **Source:** [market_data/loading/ticks.py:660](../../../../market_data/loading/ticks.py#L660)

**Inputs and outputs:**

- **Args:**

  ```text
  ts: Ts used by the operation described above.
  ```

- **Returns:**

  ```text
  Values returned by ``quote_at``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_quote_at_exact_tick`](../../../../tests/unit/market_data/test_ticks.py#L60)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_quote_at_exact_tick():
    book = _make_book()
    ts = pd.Timestamp("2025-01-06 16:30:05", tz="UTC")
    quote = book.quote_at(ts)
    assert quote is not None
    bid, ask = quote
    assert bid == pytest.approx(100.5)
    assert ask == pytest.approx(101.1)
```

2. [test fixture: `test_quote_at_before_first_tick_returns_none`](../../../../tests/unit/market_data/test_ticks.py#L161)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_quote_at_before_first_tick_returns_none():
    book = _make_book()
    ts = pd.Timestamp("2025-01-06 16:29:00", tz="UTC")
    assert book.quote_at(ts) is None
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.quote_event_at`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return the first source-ordered quote at/after *ts* and its timestamp.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.quote_event_at` · **Source:** [market_data/loading/ticks.py:679](../../../../market_data/loading/ticks.py#L679)

**Inputs and outputs:**

- **Args:**

  ```text
  ts: Ts used by the operation described above.
  ```

- **Returns:**

  ```text
  Values returned by ``quote_event_at``, in the declared order.
  ```

**Observed usage:**

1. [test fixture: `test_action_selected_partial_tp_uses_first_source_tick_and_reconciles_ledger`](../../../../tests/integration/backtest/test_action_driven_partial_tp_tick_ledger.py#L184)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
    assert env_partial["size"] == pytest.approx(0.33)
    assert bt_partial["size"] == pytest.approx(0.33)
    remaining_after_first_target = env_open["lots"] - env_partial["size"]
    assert remaining_after_first_target == pytest.approx(0.67)
    assert bt_open["lots"] - bt_partial["size"] == pytest.approx(remaining_after_first_target)
    source_tick = tickbook.quote_event_at(first_tp_crossing)
    assert source_tick is not None
    assert source_tick[1] == env_partial["price"] == bt_partial["price"]

    for engine_name, events, final_balance, _open_event in (
        ("environment", environment_events, env.account.balance, env_open),
# … caller assertions omitted …
```

2. [test fixture: `test_equal_timestamp_quote_uses_first_source_row_across_chunks`](../../../../tests/unit/market_data/test_ticks.py#L143)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        ],
    )
    book = build_tick_book(csv_path, session_start=None, session_end=None, chunksize=1)
    tick_time = pd.Timestamp("2025-01-06 16:30:00", tz="Etc/GMT-3")

    event = book.quote_event_at(tick_time)
    fill = resolve_tick_execution(
        book,
        tick_time,
        np.random.default_rng(1729),
        max_latency_ns_exclusive=0,
# … caller assertions omitted …
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.slice`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return a sub-book covering the half-open interval [start, end).

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.slice` · **Source:** [market_data/loading/ticks.py:1015](../../../../market_data/loading/ticks.py#L1015)

**Inputs and outputs:**

- **Args:**

  ```text
  start: Start used by the operation described above.
  end: End used by the operation described above.
  ```

- **Returns:**

  ```text
  Result of return a sub-book covering the half-open interval [start, end).
  ```

**Observed usage:**

1. [production caller: `build_tick_books`](../../../../market_data/loading/tick_book_pipeline.py#L191)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
                end = inclusive_date_exclusive_end(
                    end_inclusive, source_timezone, source_clock_model
                )
                if len(combined_book):
                    start = pd.Timestamp(int(combined_book._ts[0]), unit="ns", tz="UTC")
                    combined_book = combined_book.slice(start, end)
            result[sym] = combined_book
            log.info(
                "TickBook ready: %s (%d ticks, %d partitions)", sym, len(combined_book), len(books)
            )
        elif sym not in result:
# … caller assertions omitted …
```

2. [production caller: `ticks_covering`](../../../../market_data/loading/ticks.py#L1060)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def ticks_covering(
    book: TickBook | None,
    bars: pd.DataFrame,
    *,
    source_clock_model: str = "native",
) -> TickBook | None:
    if book is None or len(book) == 0 or bars.empty:
        return None
    start = pd.Timestamp(bars.index[0])
    end = pd.Timestamp(bars.index[-1]) + pd.Timedelta(minutes=2)
    if source_clock_model != "native":
        converted = session_reference_index(pd.DatetimeIndex([start, end]), source_clock_model)
        start, end = converted[0], converted[1]
    sliced = book.slice(start, end)
    if len(sliced) == 0:
        return None
    return sliced
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
