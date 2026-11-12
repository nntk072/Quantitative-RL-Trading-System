# Market data · `loading.ticks`

This page contains 13 public callable records owned by `market_data.loading.ticks`. Status reflects the exported contract, not a promise that all internal behavior is stable.

## `TickBook`

**Kind:** class · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Sorted bid/ask lookup table backed by NumPy arrays.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook` · **Source:** [market_data/loading/ticks.py:489](../../../../market_data/loading/ticks.py#L489)

**Observed usage:**

1. [test fixture: `test_environment_and_backtest_match_on_one_shared_tick_execution_trace`](../../../../tests/integration/backtest/test_account_transition_parity.py#L449)

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

2. [test fixture: `test_environment_and_backtest_consume_actions_while_delayed_entry_is_pending`](../../../../tests/integration/backtest/test_account_transition_parity.py#L572)

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

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook` · **Source:** [market_data/loading/ticks.py:489](../../../../market_data/loading/ticks.py#L489)

**Observed usage:**

1. [test fixture: `test_environment_and_backtest_match_on_one_shared_tick_execution_trace`](../../../../tests/integration/backtest/test_account_transition_parity.py#L449)

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

2. [test fixture: `test_environment_and_backtest_consume_actions_while_delayed_entry_is_pending`](../../../../tests/integration/backtest/test_account_transition_parity.py#L572)

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

**Exact API:** {py:obj}`market_data.loading.ticks.build_tick_book` · **Source:** [market_data/loading/ticks.py:925](../../../../market_data/loading/ticks.py#L925)

**Inputs and outputs:**

- **Args:**

  ```text
  path: Path to the input file or directory.
  tz: Text or path value identifying the tz.
  session_start: Session start used by the operation described above.
  session_end: Session end used by the operation described above.
  cache_path: Path or filename identifying the cache.
  force: Whether to enable or require the force.
  chunksize: Numeric value used for the chunksize.
  price_grid_increment: Price grid increment used by the operation described above.
  diagnostics: Optional mutable counter record populated during a raw-source build.
  ```

- **Returns:**

  ```text
  Result of load an MT5 tick CSV, optionally session-filter, forward-fill, build a TickBook.
  ```

**Observed usage:**

1. [test fixture: `test_equal_timestamp_quote_uses_first_source_row_across_chunks`](../../../../tests/unit/market_data/test_ticks.py#L102)

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

2. [test fixture: `test_build_tick_book_quantizes_executable_bid_ask`](../../../../tests/unit/market_data/test_ticks.py#L669)

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

## `TickBook.bar_quotes`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Yield recorded quotes in timestamp order within a half-open bar interval.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.bar_quotes` · **Source:** [market_data/loading/ticks.py:691](../../../../market_data/loading/ticks.py#L691)

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

1. [test fixture: `test_build_tick_book_filters_nonfinite_nonpositive_and_crossed_quotes`](../../../../tests/unit/market_data/test_ticks.py#L993)

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

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.content_sha256` · **Source:** [market_data/loading/ticks.py:654](../../../../market_data/loading/ticks.py#L654)

**Inputs and outputs:**

- **Returns:**

  ```text
  SHA-256 fingerprint of ordered timestamps, bids, and asks.
  ```

**Observed usage:**

1. [test fixture: `test_tickbook_content_hash_includes_stable_quote_order`](../../../../tests/unit/market_data/test_ticks.py#L61)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_tickbook_content_hash_includes_stable_quote_order() -> None:
    book = _make_book()
    identical = TickBook(book._ts.copy(), book._bid.copy(), book._ask.copy())
    reordered = TickBook(book._ts[::-1].copy(), book._bid[::-1].copy(), book._ask[::-1].copy())

    assert book.content_sha256() == identical.content_sha256()
    assert book.content_sha256() != reordered.content_sha256()
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.delayed_exit_event`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return trigger kind, actual fill time, and delayed executable quote.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.delayed_exit_event` · **Source:** [market_data/loading/ticks.py:750](../../../../market_data/loading/ticks.py#L750)

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

1. [test fixture: `test_tick_exit_ignores_crossings_before_position_entry_time`](../../../../tests/unit/simulation/test_environment/test_tick_fill_reconciliation.py#L111)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        np.array([trigger.value], dtype=np.int64),
        np.array([94.0]),
        np.array([94.5]),
    )

    event = book.delayed_exit_event(
        start,
        direction=1,
        sl=95.0,
        tp=None,
        delay=pd.Timedelta(0),
        earliest_time=entry_time,
    )

    assert event is None
```

2. [production caller: `delayed_exit_quote`](../../../../market_data/loading/ticks.py#L742)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def delayed_exit_quote(
    self,
    bar_start: pd.Timestamp,
    direction: int,
    sl: float | None,
    tp: float | None,
    delay: pd.Timedelta,
    bar_minutes: int = 1,
) -> tuple[str, float, float] | None:
    event = self.delayed_exit_event(
        bar_start, direction, sl, tp, delay, bar_minutes=bar_minutes
    )
    if event is None:
        return None
    kind, _fill_time, bid, ask = event
    return kind, bid, ask
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.delayed_exit_quote`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Quote ``delay`` after the first tick that trades through SL or TP.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.delayed_exit_quote` · **Source:** [market_data/loading/ticks.py:714](../../../../market_data/loading/ticks.py#L714)

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

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TickBook(...)
result = instance.delayed_exit_quote(bar_start=..., direction=..., sl=..., tp=..., delay=..., bar_minutes=...)
```

**Lifecycle context:** This callable participates in `TickBook`: Sorted bid/ask lookup table backed by NumPy arrays. Related public lifecycle methods: {py:obj}`market_data.loading.ticks.TickBook.quote_at`, {py:obj}`market_data.loading.ticks.TickBook.quote_event_at`, {py:obj}`market_data.loading.ticks.TickBook.execution_quote_event_at`, {py:obj}`market_data.loading.ticks.TickBook.first_limit_execution_event`, {py:obj}`market_data.loading.ticks.TickBook.content_sha256`, {py:obj}`market_data.loading.ticks.TickBook.has_ticks_between`, {py:obj}`market_data.loading.ticks.TickBook.bar_quotes`, {py:obj}`market_data.loading.ticks.TickBook.delayed_exit_quote`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.execution_quote_event_at`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return the first quote at or after an execution arrival time.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.execution_quote_event_at` · **Source:** [market_data/loading/ticks.py:563](../../../../market_data/loading/ticks.py#L563)

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

1. [test fixture: `test_environment_and_backtest_match_on_one_shared_tick_execution_trace`](../../../../tests/integration/backtest/test_account_transition_parity.py#L536)

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

2. [tutorial example: `tick_execution · code cell 2`](../../../../docs/learn/tutorials/advanced/tick_execution.ipynb)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from market_data.loading.ticks import TickBook

t0 = pd.Timestamp("2025-01-02 14:30:00", tz="UTC")
quote_times = pd.to_datetime(
    [
        "2025-01-02 14:30:00.000Z",
        "2025-01-02 14:30:00.020Z",
        "2025-01-02 14:30:00.040Z",
        "2025-01-02 14:30:00.060Z",
    ]
)
bid = np.array([100.00, 100.02, 100.01, 99.98])
ask = bid + 0.04
book = TickBook(quote_times.asi8, bid, ask)
decision = t0 + pd.Timedelta(milliseconds=10)
arrival = decision + pd.Timedelta(milliseconds=20)
quote = book.execution_quote_event_at(arrival)
assert quote is not None
fill_time, fill_bid, fill_ask = quote
print(
    {
        "decision": decision,
        "arrival": arrival,
        "first_quote": fill_time,
        "long_buy_ask": fill_ask,
        "short_sell_bid": fill_bid,
        "spread": fill_ask - fill_bid,
    }
)
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.first_limit_execution_event`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return the earliest source-ordered quote that crosses a limit.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.first_limit_execution_event` · **Source:** [market_data/loading/ticks.py:590](../../../../market_data/loading/ticks.py#L590)

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

1. [production caller: `resolve_tick_limit_execution`](../../../../market_data/loading/ticks.py#L356)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
        0 if max_latency_ns_exclusive == 0 else int(rng.integers(0, max_latency_ns_exclusive))
    )
    arrival = submitted + pd.Timedelta(latency_ns, unit="ns")
    if arrival > expiry:
        return None
    event = book.first_limit_execution_event(
        direction,
        float(limit_price),
        arrival,
        expiry,
        require_trade_through=require_trade_through,
    )
    if event is None:
        return None
    tick_time, bid, ask = event
    return TickLimitExecutionQuote(
        order_time=submitted,
# … caller assertions omitted …
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.has_ticks_between`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return whether any quote falls in the half-open interval [start, end).

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.has_ticks_between` · **Source:** [market_data/loading/ticks.py:674](../../../../market_data/loading/ticks.py#L674)

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

**Usage status:** No statically resolved project call site or source example was found. This entry is documented as an available contract, not as a tested end-user recipe.

**Invocation shape (placeholders):**

Replace `...` with values that satisfy the input contract. This syntax guide is not a runnable example; the linked project call sites above are the verified recipes when available.

```python
instance = TickBook(...)
result = instance.has_ticks_between(start=..., end=...)
```

**Lifecycle context:** This callable participates in `TickBook`: Sorted bid/ask lookup table backed by NumPy arrays. Related public lifecycle methods: {py:obj}`market_data.loading.ticks.TickBook.quote_at`, {py:obj}`market_data.loading.ticks.TickBook.quote_event_at`, {py:obj}`market_data.loading.ticks.TickBook.execution_quote_event_at`, {py:obj}`market_data.loading.ticks.TickBook.first_limit_execution_event`, {py:obj}`market_data.loading.ticks.TickBook.content_sha256`, {py:obj}`market_data.loading.ticks.TickBook.has_ticks_between`, {py:obj}`market_data.loading.ticks.TickBook.bar_quotes`, {py:obj}`market_data.loading.ticks.TickBook.delayed_exit_quote`

The input, output, and error contract above is the safe boundary for a caller. Follow the source and domain guide before integrating it; this page does not invent example values or side effects.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.quote_at`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return ``(bid, ask)`` for the first tick at or after *ts*.

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.quote_at` · **Source:** [market_data/loading/ticks.py:517](../../../../market_data/loading/ticks.py#L517)

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

1. [test fixture: `test_quote_at_exact_tick`](../../../../tests/unit/market_data/test_ticks.py#L49)

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

2. [test fixture: `test_quote_at_before_first_tick_returns_none`](../../../../tests/unit/market_data/test_ticks.py#L123)

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

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.quote_event_at` · **Source:** [market_data/loading/ticks.py:536](../../../../market_data/loading/ticks.py#L536)

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

1. [test fixture: `test_equal_timestamp_quote_uses_first_source_row_across_chunks`](../../../../tests/unit/market_data/test_ticks.py#L105)

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

2. [test fixture: `test_quote_at_after_last_tick_returns_none_instead_of_stale_quote`](../../../../tests/unit/market_data/test_ticks.py#L130)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def test_quote_at_after_last_tick_returns_none_instead_of_stale_quote():
    book = _make_book()
    ts = pd.Timestamp("2025-01-06 16:30:11", tz="UTC")
    assert book.quote_at(ts) is None
    assert book.quote_event_at(ts) is None
```

These excerpts demonstrate the API with the named project fixtures; adapt their setup to the documented contract before reusing them.

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`

## `TickBook.slice`

**Kind:** method · **Status:** stable · **Owner:** `market_data.loading.ticks`

**Purpose:** Return a sub-book covering the half-open interval [start, end).

**Exact API:** {py:obj}`market_data.loading.ticks.TickBook.slice` · **Source:** [market_data/loading/ticks.py:814](../../../../market_data/loading/ticks.py#L814)

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

1. [production caller: `build_tick_books`](../../../../market_data/loading/tick_book_pipeline.py#L149)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
# … caller setup omitted …
            )
            if end_inclusive is not None:
                end = inclusive_date_exclusive_end(end_inclusive, str(cfg.data.tz))
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

2. [production caller: `ticks_covering`](../../../../market_data/loading/ticks.py#L850)

Source excerpt (not standalone); follow the linked caller for imports and setup.

```python
def ticks_covering(book: TickBook | None, bars: pd.DataFrame) -> TickBook | None:
    if book is None or len(book) == 0 or bars.empty:
        return None
    start = pd.Timestamp(bars.index[0])
    end = pd.Timestamp(bars.index[-1]) + pd.Timedelta(minutes=2)
    sliced = book.slice(start, end)
    if len(sliced) == 0:
        return None
    return sliced
```

**Workflow context:**

- Semantic domain guide: {doc}`../../domains/data`
- Generated package reference: {doc}`../../generated/market_data/index`
