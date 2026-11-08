"""Real-tick bid/ask execution book.

``TickBook`` provides ``quote_at(ts) → (bid, ask)`` using the first tick at or
after a given timestamp. It never forward-fills beyond the last recorded tick;
callers must treat a missing quote as unavailable execution data.

Typical use
-----------
::

    tick_book = build_tick_book(
        path,
        tz="Etc/GMT-3",
        cache_path=f"cache/US100.cash_ticks_{TICK_CACHE_VERSION}.parquet",
    )
    train_ticks = tick_book.slice(pd.Timestamp("2025-01-01", tz="Etc/GMT-3"),
                                  pd.Timestamp("2025-12-31 23:59", tz="Etc/GMT-3"))
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from artifacts.identity import file_sha256
from market_data.cache.ticks import build_tick_cache_identity, load_tick_cache, write_tick_cache
from market_data.loading.bars import iter_ticks_chunks
from market_data.transforms.price_grid import price_grid_identity, quantize_prices

log = logging.getLogger(__name__)
TICK_CACHE_VERSION = "v7-source-precision-quotes"


@dataclass(frozen=True, slots=True)
class TickExecutionQuote:
    """A causal tick quote selected after a sampled order-arrival latency."""

    order_time: pd.Timestamp
    arrival_time: pd.Timestamp
    tick_time: pd.Timestamp
    bid: float
    ask: float
    latency_ns: int


@dataclass(frozen=True, slots=True)
class TickDeadlineExecutionQuote:
    """A tick quote selected after a scheduled-close order submission."""

    order_time: pd.Timestamp
    arrival_time: pd.Timestamp
    tick_time: pd.Timestamp
    bid: float
    ask: float
    latency_ns: int


@dataclass(frozen=True, slots=True)
class TickLimitExecutionQuote:
    """First executable quote satisfying a resting limit before expiry."""

    order_time: pd.Timestamp
    arrival_time: pd.Timestamp
    tick_time: pd.Timestamp
    bid: float
    ask: float
    limit_price: float
    latency_ns: int


@dataclass(frozen=True, slots=True)
class TickExitExecution:
    """A protective exit trigger and its latency-adjusted executable quote."""

    kind: str
    trigger_time: pd.Timestamp
    quote: TickExecutionQuote


class TickExecutionUnavailable(RuntimeError):
    """Raised when an order cannot be matched to an admissible later tick."""


@dataclass(slots=True)
class TickBookBuildDiagnostics:
    """Optional counts for raw quote validity and TickBook carry-forward."""

    source_rows_read: int = 0
    rows_after_session_filter: int = 0
    raw_valid_two_sided_quotes: int = 0
    raw_rows_with_missing_or_nonpositive_side: int = 0
    raw_rows_with_crossed_sides: int = 0
    rows_with_bid_carried_into_valid_quote: int = 0
    rows_with_ask_carried_into_valid_quote: int = 0
    rows_with_any_side_carried_into_valid_quote: int = 0
    rows_retained_after_carry: int = 0
    rows_dropped_for_unavailable_side_after_carry: int = 0
    rows_dropped_for_crossed_pair_after_carry: int = 0


def event_keyed_execution_rng(execution_seed: int, event_key: str) -> np.random.Generator:
    """Create a stable latency RNG for the same logical event across engines.

    Separate execution paths can consume different numbers of draws while
    advancing bars. Keying scheduled events prevents unrelated quote lookups
    from changing the sampled latency for that event.

    Args:
        execution_seed: Shared seed for execution randomness.
        event_key: Stable identity of the logical execution event.

    Returns:
        NumPy generator deterministic for this seed and event key.
    """
    digest = hashlib.sha256(f"{int(execution_seed)}:{event_key}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:16], byteorder="big"))


def limit_entry_execution_rng(
    execution_seed: int,
    order_time: pd.Timestamp,
    direction: int,
    limit_price: float,
    candidate_id: int | None,
) -> np.random.Generator:
    """Key limit-entry latency by shared order intent, not engine-local IDs.

    Environment and event-backtest order IDs use different counters. Using
    either in the random key would break paired fill parity when latency is
    sampled. The submission instant, side, stable candidate ID, and exact
    submitted price identify the same order intent across both engines.

    Args:
        execution_seed: Seed shared by paired simulator executions.
        order_time: Time at which the order becomes active.
        direction: Signed side, +1 for long or -1 for short.
        limit_price: Submitted hard limit price.
        candidate_id: Stable setup ID, or ``None`` for a non-categorical order.

    Returns:
        A deterministic generator keyed to the shared order intent.

    Raises:
        ValueError: If time, side, limit price, or candidate ID is invalid.
    """
    submitted = pd.Timestamp(order_time)
    if submitted.tz is None:
        raise ValueError("limit order time must be timezone-aware")
    if direction not in (-1, 1):
        raise ValueError("limit order direction must be -1 or +1")
    if not np.isfinite(limit_price) or limit_price <= 0.0:
        raise ValueError("limit_price must be finite and positive")
    if candidate_id is not None and (
        isinstance(candidate_id, bool)
        or not isinstance(candidate_id, (int, np.integer))
        or candidate_id < 0
    ):
        raise ValueError("candidate_id must be a nonnegative integer or None")
    candidate_key = "none" if candidate_id is None else str(int(candidate_id))
    event_key = (
        f"limit_entry:{submitted.value}:{direction}:{candidate_key}:{float(limit_price).hex()}"
    )
    return event_keyed_execution_rng(execution_seed, event_key)


def resolve_tick_execution(
    book: TickBook,
    order_time: pd.Timestamp,
    rng: np.random.Generator,
    *,
    max_latency_ns_exclusive: int = 30_000_000,
    max_quote_wait_ns: int | None = 60_000_000_000,
) -> TickExecutionQuote | None:
    """Apply optional sub-30 ms latency and select the first eligible tick.

    A positive latency bound samples uniformly over integer nanoseconds in
    ``[0, max_latency_ns_exclusive)``; a zero bound means zero delay. The
    selected quote is the first tick at or after arrival; a pre-arrival quote
    is never eligible.
    The caller must treat ``None`` as unavailable tick execution, not substitute
    a candle quote.

    Args:
        book: Book used by the operation described above.
        order_time: Order time used by the operation described above.
        rng: Rng used by the operation described above.
        max_latency_ns_exclusive: Numeric value used for the max latency ns exclusive.
        max_quote_wait_ns: Max quote wait ns used by the operation described above.

    Returns:
        Result of apply optional sub-30 ms latency and select the first eligible tick.
    """
    if max_latency_ns_exclusive < 0:
        raise ValueError("max_latency_ns_exclusive cannot be negative")
    submitted = pd.Timestamp(order_time)
    # A zero-latency order still executes from the first observed tick at or
    # after submission. Zero disables random delay; it never enables candle
    # pricing.
    latency_ns = (
        0 if max_latency_ns_exclusive == 0 else int(rng.integers(0, max_latency_ns_exclusive))
    )
    arrival = submitted + pd.Timedelta(latency_ns, unit="ns")
    # Execution differs from a valuation lookup: if the order arrives just
    # before the first observed tick, that first tick is still the first
    # executable quote at or after arrival. ``quote_event_at`` intentionally
    # treats pre-coverage timestamps as unavailable for ordinary lookups.
    event = book.execution_quote_event_at(arrival)
    if event is None:
        return None
    tick_time, bid, ask = event
    if tick_time < arrival:
        raise RuntimeError("TickBook returned a pre-arrival quote for execution")
    if max_quote_wait_ns is not None and tick_time.value - arrival.value > max_quote_wait_ns:
        return None
    return TickExecutionQuote(
        order_time=submitted,
        arrival_time=arrival,
        tick_time=tick_time,
        bid=bid,
        ask=ask,
        latency_ns=latency_ns,
    )


def resolve_tick_execution_by_deadline(
    book: TickBook,
    submission_time: pd.Timestamp,
    deadline: pd.Timestamp,
    rng: np.random.Generator,
    *,
    max_latency_ns_exclusive: int = 30_000_000,
    max_quote_wait_ns: int | None = 60_000_000_000,
) -> TickDeadlineExecutionQuote | None:
    """Resolve a scheduled close using only a quote after sampled arrival.

    The close is known in advance, so callers can submit at the start of the
    final interval. The first observed quote at or after sampled arrival must
    occur by the deadline and within the quote-wait limit. A pre-arrival quote
    is never an executable substitute when the market stops quoting before
    the order arrives.

    Args:
        book: Book used by the operation described above.
        submission_time: Submission time used by the operation described above.
        deadline: Deadline used by the operation described above.
        rng: Rng used by the operation described above.
        max_latency_ns_exclusive: Numeric value used for the max latency ns exclusive.
        max_quote_wait_ns: Max quote wait ns used by the operation described above.

    Returns:
        Result of resolve a scheduled close using only a quote after sampled arrival.
    """
    if max_latency_ns_exclusive < 0:
        raise ValueError("max_latency_ns_exclusive cannot be negative")
    end = pd.Timestamp(deadline)
    lead_ns = max_latency_ns_exclusive
    submitted = pd.Timestamp(submission_time)
    if submitted.tz is None or end.tz is None:
        raise ValueError("deadline execution timestamps must be timezone-aware")
    if submitted > end:
        raise ValueError("submission_time cannot be after deadline")
    latency_ns = 0 if lead_ns == 0 else int(rng.integers(0, lead_ns))
    arrival = submitted + pd.Timedelta(latency_ns, unit="ns")

    event = book.execution_quote_event_at(arrival)
    if event is not None:
        tick_time, bid, ask = event
        if tick_time <= end and (
            max_quote_wait_ns is None or tick_time.value - arrival.value <= max_quote_wait_ns
        ):
            return TickDeadlineExecutionQuote(
                order_time=submitted,
                arrival_time=arrival,
                tick_time=tick_time,
                bid=bid,
                ask=ask,
                latency_ns=latency_ns,
            )

    return None


def resolve_tick_limit_execution(
    book: TickBook,
    direction: int,
    limit_price: float,
    order_time: pd.Timestamp,
    expiry_time: pd.Timestamp,
    rng: np.random.Generator,
    *,
    max_latency_ns_exclusive: int = 0,
    require_trade_through: bool = False,
) -> TickLimitExecutionQuote | None:
    """Find the first observed executable quote at a resting limit by expiry.

    A buy limit is executable when the observed ask reaches or passes below the
    limit; a sell limit is executable when bid reaches or passes above it.
    ``require_trade_through`` excludes a quote exactly at the limit, providing
    a stricter sensitivity case for the absence of queue-position data.

    Args:
        book: Ordered local bid/ask observations.
        direction: +1 for a buy limit and -1 for a sell limit.
        limit_price: Maximum buy price or minimum sell price.
        order_time: Time at which the order is submitted.
        expiry_time: Inclusive final time at which the order can fill.
        rng: Random generator used to sample submission latency.
        max_latency_ns_exclusive: Upper-exclusive submission latency in ns.
        require_trade_through: Require ask < limit for buys or bid > limit for sells.

    Returns:
        The first source-ordered executable quote, or None when it never arrives.
    """
    if direction not in (-1, 1):
        raise ValueError("limit order direction must be -1 or +1")
    if not np.isfinite(limit_price) or limit_price <= 0.0:
        raise ValueError("limit_price must be finite and positive")
    if max_latency_ns_exclusive < 0:
        raise ValueError("max_latency_ns_exclusive cannot be negative")
    submitted = pd.Timestamp(order_time)
    expiry = pd.Timestamp(expiry_time)
    if submitted.tz is None or expiry.tz is None:
        raise ValueError("limit order timestamps must be timezone-aware")
    if expiry < submitted:
        raise ValueError("expiry_time cannot precede order_time")
    latency_ns = (
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
        arrival_time=arrival,
        tick_time=tick_time,
        bid=bid,
        ask=ask,
        limit_price=float(limit_price),
        latency_ns=latency_ns,
    )


def resolve_tick_exit(
    book: TickBook,
    bar_start: pd.Timestamp,
    direction: int,
    sl: float | None,
    tp: float | None,
    rng: np.random.Generator,
    *,
    bar_minutes: int = 1,
    earliest_time: pd.Timestamp | None = None,
    max_latency_ns_exclusive: int = 30_000_000,
    max_quote_wait_ns: int | None = 60_000_000_000,
    event_seed: int | None = None,
    server_side_protective: bool = False,
) -> TickExitExecution | None:
    """Resolve the first tick-triggered SL/TP after randomized execution latency.

    Stop wins if a single tick is beyond both levels. Once a trigger is found,
    execution uses the first quote at or after the sampled arrival time. A
    triggered order without a timely subsequent quote raises rather than
    silently becoming a candle-priced fill.

    Args:
        book: Book used by the operation described above.
        bar_start: Bar start used by the operation described above.
        direction: Signed trade direction: 1 for long and -1 for short.
        sl: Sl used by the operation described above.
        tp: Tp used by the operation described above.
        rng: Rng used by the operation described above.
        bar_minutes: Numeric value used for the bar minutes.
        earliest_time: Earliest time used by the operation described above.
        max_latency_ns_exclusive: Numeric value used for the max latency ns exclusive.
        max_quote_wait_ns: Max quote wait ns used by the operation described above.
        event_seed: Optional stable seed for trigger-keyed latency independent of
            unrelated execution RNG draws.
        server_side_protective: Execute an already-attached protective order on the
            triggering source quote without sampling a new network latency.

    Returns:
        Result of resolve the first tick-triggered SL/TP after randomized execution latency.
    """
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")
    start = pd.Timestamp(bar_start)
    start_ns = start.value
    if earliest_time is not None:
        start_ns = max(start_ns, pd.Timestamp(earliest_time).value)
    end_ns = start.value + int(pd.Timedelta(minutes=bar_minutes).value)
    i0 = int(np.searchsorted(book._ts, start_ns, side="left"))
    i1 = int(np.searchsorted(book._ts, end_ns, side="left"))
    if i0 >= i1:
        return None

    side = book._bid if direction == 1 else book._ask
    for i in range(i0, i1):
        price = float(side[i])
        sl_cross = sl is not None and (
            (direction == 1 and price <= sl) or (direction == -1 and price >= sl)
        )
        tp_cross = tp is not None and (
            (direction == 1 and price >= tp) or (direction == -1 and price <= tp)
        )
        if not sl_cross and not tp_cross:
            continue
        kind = "sl" if sl_cross else "tp"
        trigger_time = pd.Timestamp(int(book._ts[i]), unit="ns", tz="UTC")
        if server_side_protective:
            # Resting protective order is already at the server. Do not apply
            # the EA request/response network delay. Preserve the precise source
            # row when multiple quote changes share the same millisecond.
            instant_quote = TickExecutionQuote(
                order_time=trigger_time,
                arrival_time=trigger_time,
                tick_time=trigger_time,
                bid=float(book._bid[i]),
                ask=float(book._ask[i]),
                latency_ns=0,
            )
            return TickExitExecution(kind=kind, trigger_time=trigger_time, quote=instant_quote)
        event_rng = (
            rng
            if event_seed is None
            else event_keyed_execution_rng(
                int(event_seed), f"protective_exit:{direction}:{kind}:{trigger_time.value}"
            )
        )
        quote = resolve_tick_execution(
            book,
            trigger_time,
            event_rng,
            max_latency_ns_exclusive=max_latency_ns_exclusive,
            max_quote_wait_ns=max_quote_wait_ns,
        )
        if quote is None:
            raise TickExecutionUnavailable(
                f"{kind.upper()} triggered at {trigger_time}, but no timely quote "
                "exists after its sampled order-arrival time"
            )
        return TickExitExecution(kind=kind, trigger_time=trigger_time, quote=quote)
    return None


def _ffill_inplace(arr: np.ndarray[Any, Any]) -> None:
    """In-place forward-fill of NaNs in a 1-D float array (no pandas).

    Args:
        arr: Arr used by the operation described above.
    """
    mask = np.isnan(arr)
    if not mask.any():
        return
    idx = np.where(~mask, np.arange(len(arr)), 0)
    np.maximum.accumulate(idx, out=idx)
    arr[:] = arr[idx]


class TickBook:
    """Sorted bid/ask lookup table backed by NumPy arrays.

    For equal stored timestamps, stable source-row order is retained and
    lookups select the first source-ordered quote. This is a deterministic
    tie-break for millisecond timestamps, not a claim about sub-millisecond
    chronology.
    """

    __slots__ = ("_ts", "_bid", "_ask")

    def __init__(
        self,
        ts_ns: np.ndarray[Any, Any],
        bid: np.ndarray[Any, Any],
        ask: np.ndarray[Any, Any],
    ) -> None:
        """Initialize TickBook and its owned state.

        Args:
            ts_ns: Ts ns used by the operation described above.
            bid: Bid used by the operation described above.
            ask: Ask used by the operation described above.
        """
        self._ts = ts_ns
        self._bid = bid
        self._ask = ask

    def quote_at(self, ts: pd.Timestamp) -> tuple[float, float] | None:
        """Return ``(bid, ask)`` for the first tick at or after *ts*.

        Returns ``None`` when *ts* is outside the recorded tick interval,
        including after the final recorded tick. A caller must not reuse a
        stale final quote as an execution price.

        Args:
            ts: Ts used by the operation described above.

        Returns:
            Values returned by ``quote_at``, in the declared order.
        """
        event = self.quote_event_at(ts)
        if event is None:
            return None
        _quote_time, bid, ask = event
        return bid, ask

    def quote_event_at(self, ts: pd.Timestamp) -> tuple[pd.Timestamp, float, float] | None:
        """Return the first source-ordered quote at/after *ts* and its timestamp.

        If several source rows share the selected millisecond timestamp, the
        first row in the stable TickBook order is returned.

        Args:
            ts: Ts used by the operation described above.

        Returns:
            Values returned by ``quote_event_at``, in the declared order.
        """
        n = len(self._ts)
        if n == 0:
            return None
        ts_ns = ts.value
        if ts_ns < self._ts[0]:
            return None
        i = int(np.searchsorted(self._ts, ts_ns, side="left"))
        if i >= n:
            return None
        return (
            pd.Timestamp(int(self._ts[i]), unit="ns", tz="UTC"),
            float(self._bid[i]),
            float(self._ask[i]),
        )

    def execution_quote_event_at(
        self, ts: pd.Timestamp
    ) -> tuple[pd.Timestamp, float, float] | None:
        """Return the first quote at or after an execution arrival time.

        Unlike ``quote_event_at``, this permits an arrival timestamp earlier
        than the first stored tick. Callers still need a finite quote-wait
        limit so that a distant first observation cannot masquerade as a fill.

        Args:
            ts: Ts used by the operation described above.

        Returns:
            Values returned by ``execution_quote_event_at``, in the declared order.
        """
        n = len(self._ts)
        if n == 0:
            return None
        i = int(np.searchsorted(self._ts, pd.Timestamp(ts).value, side="left"))
        if i >= n:
            return None
        return (
            pd.Timestamp(int(self._ts[i]), unit="ns", tz="UTC"),
            float(self._bid[i]),
            float(self._ask[i]),
        )

    def first_limit_execution_event(
        self,
        direction: int,
        limit_price: float,
        start_time: pd.Timestamp,
        expiry_time: pd.Timestamp,
        *,
        require_trade_through: bool = False,
    ) -> tuple[pd.Timestamp, float, float] | None:
        """Return the earliest source-ordered quote that crosses a limit.

        Tick data does not contain queue position or displayed depth. The
        returned crossing is therefore a quote-based fill model, not proof of
        broker queue priority. Callers can require trade-through for a stricter
        sensitivity analysis.

        Args:
            direction: Limit-order side, ``1`` for buy or ``-1`` for sell.
            limit_price: Submitted limit price.
            start_time: Earliest timestamp eligible for a fill.
            expiry_time: Last timestamp eligible for a fill, inclusive.
            require_trade_through: Whether a quote must cross beyond the limit.

        Returns:
            Earliest matching timestamp and its bid/ask, or ``None`` if unfilled.
        """
        if direction not in (-1, 1):
            raise ValueError("limit order direction must be -1 or +1")
        if not np.isfinite(limit_price) or limit_price <= 0.0:
            raise ValueError("limit_price must be finite and positive")
        start = pd.Timestamp(start_time)
        expiry = pd.Timestamp(expiry_time)
        if start.tz is None or expiry.tz is None:
            raise ValueError("limit order timestamps must be timezone-aware")
        if expiry < start:
            raise ValueError("expiry_time cannot precede start_time")
        first = int(np.searchsorted(self._ts, start.value, side="left"))
        last = int(np.searchsorted(self._ts, expiry.value, side="right"))
        if first >= last:
            return None
        bid = self._bid[first:last]
        ask = self._ask[first:last]
        if direction == 1:
            eligible = ask < limit_price if require_trade_through else ask <= limit_price
        else:
            eligible = bid > limit_price if require_trade_through else bid >= limit_price
        matches = np.flatnonzero(eligible)
        if matches.size == 0:
            return None
        index = first + int(matches[0])
        return (
            pd.Timestamp(int(self._ts[index]), unit="ns", tz="UTC"),
            float(self._bid[index]),
            float(self._ask[index]),
        )

    def __len__(self) -> int:
        """Process TickBook.

        Returns:
            Numeric result returned by ``__len__``.
        """
        return len(self._ts)

    def content_sha256(self) -> str:
        """Fingerprint the ordered timestamp and quote arrays used for execution.

        Equal-timestamp source order affects quote selection, so the digest
        includes array order, dtype, and shape for all three owned arrays.

        Returns:
            SHA-256 fingerprint of ordered timestamps, bids, and asks.
        """
        digest = hashlib.sha256(b"qrl.tickbook.content.v1\0")
        for name, values in ((b"timestamp_ns", self._ts), (b"bid", self._bid), (b"ask", self._ask)):
            contiguous = np.ascontiguousarray(values)
            digest.update(name)
            digest.update(b"\0")
            digest.update(str(contiguous.dtype).encode("ascii"))
            digest.update(b"\0")
            digest.update(np.asarray(contiguous.shape, dtype="<i8").tobytes())
            digest.update(contiguous.tobytes())
        return digest.hexdigest()

    def has_ticks_between(self, start: pd.Timestamp, end: pd.Timestamp) -> bool:
        """Return whether any quote falls in the half-open interval [start, end).

        Args:
            start: Start used by the operation described above.
            end: End used by the operation described above.

        Returns:
            Whether has ticks between meets the requested condition.
        """
        start_ns = pd.Timestamp(start).value
        end_ns = pd.Timestamp(end).value
        if end_ns <= start_ns or len(self._ts) == 0:
            return False
        i0 = int(np.searchsorted(self._ts, start_ns, side="left"))
        return i0 < len(self._ts) and int(self._ts[i0]) < end_ns

    def bar_quotes(
        self, bar_start: pd.Timestamp, bar_minutes: int = 1
    ) -> Iterator[tuple[pd.Timestamp, float, float]]:
        """Yield recorded quotes in timestamp order within a half-open bar interval.

        Args:
            bar_start: Bar start used by the operation described above.
            bar_minutes: Numeric value used for the bar minutes.

        Yields:
            Each bar quotes value, yielded in processing order.
        """
        start_ns = pd.Timestamp(bar_start).value
        end_ns = start_ns + int(pd.Timedelta(minutes=bar_minutes).value)
        i0 = int(np.searchsorted(self._ts, start_ns, side="left"))
        i1 = int(np.searchsorted(self._ts, end_ns, side="left"))
        for idx in range(i0, i1):
            yield (
                pd.Timestamp(int(self._ts[idx]), unit="ns", tz="UTC"),
                float(self._bid[idx]),
                float(self._ask[idx]),
            )

    def delayed_exit_quote(
        self,
        bar_start: pd.Timestamp,
        direction: int,
        sl: float | None,
        tp: float | None,
        delay: pd.Timedelta,
        bar_minutes: int = 1,
    ) -> tuple[str, float, float] | None:
        """Quote ``delay`` after the first tick that trades through SL or TP.

        A long exit watches the bid; a short exit watches the ask. The first
        tick beyond either level is the trigger, so a target that prints
        before the stop wins. Delay 0 fills that crossing tick, which is
        already through the level. Returns ``None`` when the bar has no
        crossing tick.

        Args:
            bar_start: Bar start used by the operation described above.
            direction: Signed trade direction: 1 for long and -1 for short.
            sl: Sl used by the operation described above.
            tp: Tp used by the operation described above.
            delay: Delay used by the operation described above.
            bar_minutes: Numeric value used for the bar minutes.

        Returns:
            Values returned by ``delayed_exit_quote``, in the declared order.
        """
        event = self.delayed_exit_event(
            bar_start, direction, sl, tp, delay, bar_minutes=bar_minutes
        )
        if event is None:
            return None
        kind, _fill_time, bid, ask = event
        return kind, bid, ask

    def delayed_exit_event(
        self,
        bar_start: pd.Timestamp,
        direction: int,
        sl: float | None,
        tp: float | None,
        delay: pd.Timedelta,
        bar_minutes: int = 1,
        earliest_time: pd.Timestamp | None = None,
    ) -> tuple[str, pd.Timestamp, float, float] | None:
        """Return trigger kind, actual fill time, and delayed executable quote.

        Args:
            bar_start: Bar start used by the operation described above.
            direction: Signed trade direction: 1 for long and -1 for short.
            sl: Sl used by the operation described above.
            tp: Tp used by the operation described above.
            delay: Delay used by the operation described above.
            bar_minutes: Numeric value used for the bar minutes.
            earliest_time: Earliest time used by the operation described above.

        Returns:
            Values returned by ``delayed_exit_event``, in the declared order.
        """
        n = len(self._ts)
        if n == 0 or direction not in (1, -1):
            return None
        start_ns = pd.Timestamp(bar_start).value
        if earliest_time is not None:
            start_ns = max(start_ns, pd.Timestamp(earliest_time).value)
        end_ns = pd.Timestamp(bar_start).value + int(pd.Timedelta(minutes=bar_minutes).value)
        i0 = int(np.searchsorted(self._ts, start_ns, side="left"))
        i1 = int(np.searchsorted(self._ts, end_ns, side="left"))
        if i0 >= i1:
            return None
        side = self._bid if direction == 1 else self._ask
        trigger = -1
        kind = ""
        for i in range(i0, i1):
            px = float(side[i])
            sl_cross = sl is not None and (
                (direction == 1 and px <= sl) or (direction == -1 and px >= sl)
            )
            tp_cross = tp is not None and (
                (direction == 1 and px >= tp) or (direction == -1 and px <= tp)
            )
            if sl_cross:
                trigger = i
                kind = "sl"
                break
            if tp_cross:
                trigger = i
                kind = "tp"
                break
        if trigger < 0:
            return None
        fill_ns = int(self._ts[trigger]) + int(pd.Timedelta(delay).value)
        fill_time = pd.Timestamp(fill_ns, unit="ns", tz="UTC")
        quote_event = self.quote_event_at(fill_time)
        if quote_event is None:
            return None
        quote_time, bid, ask = quote_event
        return kind, max(fill_time, quote_time), bid, ask

    def slice(self, start: pd.Timestamp, end: pd.Timestamp) -> TickBook:
        """Return a sub-book covering the half-open interval [start, end).

        Args:
            start: Start used by the operation described above.
            end: End used by the operation described above.

        Returns:
            Result of return a sub-book covering the half-open interval [start, end).
        """
        i_s = int(np.searchsorted(self._ts, start.value, side="left"))
        i_e = int(np.searchsorted(self._ts, end.value, side="left"))
        return TickBook(
            self._ts[i_s:i_e].copy(),
            self._bid[i_s:i_e].copy(),
            self._ask[i_s:i_e].copy(),
        )


def ticks_covering(book: TickBook | None, bars: pd.DataFrame) -> TickBook | None:
    """Slice *book* to the bars, plus one extra minute for the fill delay.

    An empty slice means this window has no tape, so the caller keeps the
    level fill.

    Args:
        book: Book used by the operation described above.
        bars: Market bars to process.

    Returns:
        Result of slice *book* to the bars, plus one extra minute for the fill delay.
    """
    if book is None or len(book) == 0 or bars.empty:
        return None
    start = pd.Timestamp(bars.index[0])
    end = pd.Timestamp(bars.index[-1]) + pd.Timedelta(minutes=2)
    sliced = book.slice(start, end)
    if len(sliced) == 0:
        return None
    return sliced


def tick_execution_coverage(
    book: TickBook | None,
    order_times: pd.DatetimeIndex,
    *,
    max_latency_ns_exclusive: int,
    max_quote_wait_ms: int,
) -> dict[str, Any]:
    """Measure whether every candidate order time has a timely executable tick.

    For a positive latency bound, coverage is guaranteed for every latency in
    ``[0, max_latency)`` when a valid quote follows the latest possible
    arrival within ``max_quote_wait``. A zero bound checks the immediate order
    time. This is a conservative preflight for environments requiring tick
    quotes at each candidate market step.

    Args:
        book: Book used by the operation described above.
        order_times: Order times used by the operation described above.
        max_latency_ns_exclusive: Numeric value used for the max latency ns exclusive.
        max_quote_wait_ms: Numeric value used for the max quote wait ms.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    if max_latency_ns_exclusive < 0 or max_latency_ns_exclusive > 30_000_000:
        raise ValueError("max_latency_ns_exclusive must be in [0, 30_000_000]")
    if max_quote_wait_ms <= 0:
        raise ValueError("max_quote_wait_ms must be positive")
    if order_times.tz is None:
        raise ValueError("order_times must be timezone-aware")

    order_ns = order_times.to_numpy(dtype="datetime64[ns]").astype(np.int64)
    if order_ns.size == 0:
        return {
            "order_count": 0,
            "covered_count": 0,
            "unavailable_count": 0,
            "coverage_fraction": 1.0,
            "first_unavailable_order_time": None,
        }

    covered = np.zeros(order_ns.size, dtype=bool)
    if book is not None and len(book) > 0:
        latest_arrival_ns = (
            order_ns if max_latency_ns_exclusive == 0 else order_ns + max_latency_ns_exclusive - 1
        )
        candidate_idx = np.searchsorted(book._ts, latest_arrival_ns, side="left")
        has_quote = candidate_idx < len(book)
        if has_quote.any():
            covered[has_quote] = (
                book._ts[candidate_idx[has_quote]] - order_ns[has_quote]
                <= max_quote_wait_ms * 1_000_000
            )

    unavailable = np.flatnonzero(~covered)
    first_missing = (
        None
        if unavailable.size == 0
        else pd.Timestamp(int(order_ns[unavailable[0]]), unit="ns", tz="UTC").isoformat()
    )
    return {
        "order_count": int(order_ns.size),
        "covered_count": int(covered.sum()),
        "unavailable_count": int(unavailable.size),
        "coverage_fraction": float(covered.mean()),
        "first_unavailable_order_time": first_missing,
    }


def build_tick_book(
    path: str | Path,
    tz: str = "Etc/GMT-3",
    session_start: str | None = None,
    session_end: str | None = None,
    cache_path: str | Path | None = None,
    force: bool = False,
    chunksize: int = 2_000_000,
    price_grid_increment: float | None = None,
    diagnostics: TickBookBuildDiagnostics | None = None,
) -> TickBook:
    """Load an MT5 tick CSV, optionally session-filter, forward-fill, build a TickBook.

    Pass ``session_start=None`` and ``session_end=None`` (the default) to keep
    ticks outside NY so overnight replay can quote skipped bars.

    Memory-safe by design
    ----------------------
    MT5 tick exports can be multiple GB.  This streams the file in bounded
    chunks (:func:`iter_ticks_chunks`) instead of materialising it whole:

    * Only ``date``/``time``/``bid``/``ask`` are read — ``last``/``volume``/
      ``flags`` are dropped at the CSV-parser level via ``usecols``.
    * ``bid``/``ask`` are read as ``float64`` so executable price-grid values
      remain comparable to float64 stop and target levels without a binary32
      rounding offset.
    * The session-hours filter is applied **per chunk**, discarding the
      ~70%+ of rows outside the trading window before they ever accumulate.
    * Forward-fill state (the last valid bid/ask) is carried across chunk
      boundaries so results are identical to a whole-file ffill.

    When ``diagnostics`` is supplied, this same streaming pass also records
    raw quote validity, side-carry restorations, and post-carry exclusions.
    These counters are intended for audit use and are not written to cache.
    Pass ``cache_path=None`` when collecting them so a cache hit cannot bypass
    source-row inspection.

    Peak memory is therefore roughly one chunk's worth of raw CSV data plus
    the final (already session-filtered, much smaller) tick arrays — not the
    full file size multiplied by pandas' usual 3-5x parsing overhead.

    Args:
        path: Path to the input file or directory.
        tz: Text or path value identifying the tz.
        session_start: Session start used by the operation described above.
        session_end: Session end used by the operation described above.
        cache_path: Path or filename identifying the cache.
        force: Whether to enable or require the force.
        chunksize: Numeric value used for the chunksize.
        price_grid_increment: Price grid increment used by the operation described above.
        diagnostics: Optional mutable counter record populated during a raw-source build.

    Returns:
        Result of load an MT5 tick CSV, optionally session-filter, forward-fill, build a TickBook.
    """
    path = Path(path)
    cache_identity: dict[str, Any] | None = None
    if cache_path:
        if diagnostics is not None:
            raise ValueError("pass cache_path=None when collecting TickBook build diagnostics")
        cache_path = Path(cache_path)
        cache_identity = build_tick_cache_identity(
            source_path=path,
            source_sha256=file_sha256(path),
            timezone=tz,
            session_start=session_start,
            session_end=session_end,
            price_grid_identity=price_grid_identity(price_grid_increment),
            cache_version=TICK_CACHE_VERSION,
        )
        cached_frame = None if force else load_tick_cache(cache_path, cache_identity)
        if cached_frame is not None:
            log.info("Loading tick cache: %s", cache_path)
            return TickBook(
                cast(np.ndarray[Any, Any], cached_frame["ts_ns"].to_numpy()),
                cast(np.ndarray[Any, Any], cached_frame["bid"].to_numpy()),
                cast(np.ndarray[Any, Any], cached_frame["ask"].to_numpy()),
            )

    log.info("Building TickBook from %s (chunked, memory-safe) …", path)

    start_t = (
        pd.Timestamp(f"2000-01-01 {session_start}").time() if session_start is not None else None
    )
    end_t = pd.Timestamp(f"2000-01-01 {session_end}").time() if session_end is not None else None

    ts_chunks: list[np.ndarray[Any, Any]] = []
    bid_chunks: list[np.ndarray[Any, Any]] = []
    ask_chunks: list[np.ndarray[Any, Any]] = []

    last_bid = np.nan
    last_ask = np.nan
    n_rows_total = 0
    n_rows_kept = 0

    for raw_chunk in iter_ticks_chunks(path, chunksize=chunksize):
        n_rows_total += len(raw_chunk)
        if diagnostics is not None:
            diagnostics.source_rows_read += len(raw_chunk)

        # Chunk-local datetime parse (bounded memory) — Etc/GMT-3 etc. are
        # fixed-offset zones (no DST), so tz_localize here is unambiguous
        # regardless of how the file happens to be chunked.  MT5 tick time
        # includes milliseconds (HH:MM:SS.fff), unlike bar files.
        dt = pd.to_datetime(
            raw_chunk["date"].to_numpy() + " " + raw_chunk["time"].to_numpy(),
            format="%Y.%m.%d %H:%M:%S.%f",
        )
        dt = dt.tz_localize(tz)

        if start_t is not None and end_t is not None:
            t = dt.time
            mask = (t >= start_t) & (t <= end_t)
            if not mask.any():
                continue
        else:
            mask = np.ones(len(dt), dtype=bool)

        if diagnostics is not None:
            diagnostics.rows_after_session_filter += int(mask.sum())

        bid = raw_chunk["bid"].to_numpy(dtype=np.float64, copy=True)[mask]
        ask = raw_chunk["ask"].to_numpy(dtype=np.float64, copy=True)[mask]
        ts_ns = dt.values.astype("int64")[mask]

        raw_bid_valid = np.isfinite(bid) & (bid > 0.0)
        raw_ask_valid = np.isfinite(ask) & (ask > 0.0)
        raw_valid_pair = raw_bid_valid & raw_ask_valid & (ask >= bid)
        bid_needs_carry = ~raw_bid_valid
        ask_needs_carry = ~raw_ask_valid
        if diagnostics is not None:
            diagnostics.raw_valid_two_sided_quotes += int(np.count_nonzero(raw_valid_pair))
            diagnostics.raw_rows_with_missing_or_nonpositive_side += int(
                np.count_nonzero(~raw_bid_valid | ~raw_ask_valid)
            )
            diagnostics.raw_rows_with_crossed_sides += int(
                np.count_nonzero(raw_bid_valid & raw_ask_valid & (ask < bid))
            )

        # Treat non-finite and non-positive sides as missing before carrying
        # the last usable side forward. Infinity is not handled by
        # ``_ffill_inplace`` and must never enter the executable quote book.
        bid[~np.isfinite(bid) | (bid <= 0.0)] = np.nan
        ask[~np.isfinite(ask) | (ask <= 0.0)] = np.nan

        # Patch the first element with the carried-forward quote so ffill
        # is continuous across the chunk boundary.
        if len(bid):
            if np.isnan(bid[0]) and not np.isnan(last_bid):
                bid[0] = last_bid
            if np.isnan(ask[0]) and not np.isnan(last_ask):
                ask[0] = last_ask

        _ffill_inplace(bid)
        _ffill_inplace(ask)

        # A side can update independently, so temporarily crossed pairs are
        # possible while the other side catches up. Keep those side values as
        # ffill state, but do not expose an invalid pair to execution.
        bid_available = np.isfinite(bid) & (bid > 0.0)
        ask_available = np.isfinite(ask) & (ask > 0.0)
        crossed_after_carry = bid_available & ask_available & (ask < bid)
        valid = bid_available & ask_available & (ask >= bid)
        if diagnostics is not None:
            carried_bid = valid & bid_needs_carry
            carried_ask = valid & ask_needs_carry
            diagnostics.rows_with_bid_carried_into_valid_quote += int(np.count_nonzero(carried_bid))
            diagnostics.rows_with_ask_carried_into_valid_quote += int(np.count_nonzero(carried_ask))
            diagnostics.rows_with_any_side_carried_into_valid_quote += int(
                np.count_nonzero(carried_bid | carried_ask)
            )
            diagnostics.rows_retained_after_carry += int(np.count_nonzero(valid))
            diagnostics.rows_dropped_for_unavailable_side_after_carry += int(
                np.count_nonzero(~bid_available | ~ask_available)
            )
            diagnostics.rows_dropped_for_crossed_pair_after_carry += int(
                np.count_nonzero(crossed_after_carry)
            )
        if len(bid):
            last_bid, last_ask = float(bid[-1]), float(ask[-1])
        if price_grid_increment is not None:
            bid = quantize_prices(bid, price_grid_increment)
            ask = quantize_prices(ask, price_grid_increment)

        if not valid.all():
            bid, ask, ts_ns = bid[valid], ask[valid], ts_ns[valid]

        if len(bid):
            ts_chunks.append(ts_ns)
            bid_chunks.append(bid)
            ask_chunks.append(ask)
            n_rows_kept += len(bid)

    log.info(
        "Tick scan complete: kept %d / %d rows (%.1f%%)",
        n_rows_kept,
        n_rows_total,
        100.0 * n_rows_kept / max(n_rows_total, 1),
    )

    if not ts_chunks:
        ts_ns = np.array([], dtype="int64")
        bid = np.array([], dtype=np.float64)
        ask = np.array([], dtype=np.float64)
    else:
        ts_ns = np.concatenate(ts_chunks)
        bid = np.concatenate(bid_chunks).astype(np.float64)
        ask = np.concatenate(ask_chunks).astype(np.float64)
        # MT5 exports are chronological; stable sorting also preserves their
        # source-row order when several ticks share a millisecond timestamp.
        order = np.argsort(ts_ns, kind="stable")
        ts_ns, bid, ask = ts_ns[order], bid[order], ask[order]

    if cache_path and cache_identity is not None:
        write_tick_cache(
            cache_path,
            pd.DataFrame({"ts_ns": ts_ns, "bid": bid, "ask": ask}),
            cache_identity,
        )
        log.info("Tick cache written: %s (%d ticks)", cache_path, len(ts_ns))

    return TickBook(ts_ns, bid, ask)
