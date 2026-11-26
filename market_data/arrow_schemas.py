"""Physical Arrow/Parquet schemas and validators for normalized market events (DATA-SCHEMAS).

The semantics are declared by :class:`market_data.contracts.MarketEventSchema`; this module adds
the physical types. Times are UTC ``timestamp[ns]`` with an explicit source clock, an availability
time, and a source sequence used as the stable tie-breaker. Missing values are null, never
sentinel zeros. Validators return the failing row indices with reasons so that invalid records can
be quarantined rather than silently dropped.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]

SCHEMA_VERSION = "market-event.v1"

_UTC_NS = pa.timestamp("ns", tz="UTC")

QUOTE_SCHEMA = pa.schema(
    [
        pa.field("event_time", _UTC_NS, nullable=False),
        pa.field("available_at", _UTC_NS, nullable=False),
        pa.field("source_sequence", pa.int64(), nullable=False),
        pa.field("instrument_id", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("schema_id", pa.string(), nullable=False),
        pa.field("bid", pa.float64(), nullable=True),
        pa.field("ask", pa.float64(), nullable=True),
        pa.field("bid_size", pa.float64(), nullable=True),
        pa.field("ask_size", pa.float64(), nullable=True),
        pa.field("source_flags", pa.int32(), nullable=False),
    ]
)

BAR_SCHEMA = pa.schema(
    [
        pa.field("event_time", _UTC_NS, nullable=False),
        pa.field("close_time", _UTC_NS, nullable=False),
        pa.field("available_at", _UTC_NS, nullable=False),
        pa.field("source_sequence", pa.int64(), nullable=False),
        pa.field("instrument_id", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("schema_id", pa.string(), nullable=False),
        pa.field("open", pa.float64(), nullable=False),
        pa.field("high", pa.float64(), nullable=False),
        pa.field("low", pa.float64(), nullable=False),
        pa.field("close", pa.float64(), nullable=False),
        pa.field("volume", pa.float64(), nullable=True),
    ]
)

INSTRUMENT_SCHEMA = pa.schema(
    [
        pa.field("instrument_id", pa.string(), nullable=False),
        pa.field("contract_size", pa.float64(), nullable=False),
        pa.field("price_tick", pa.float64(), nullable=False),
        pa.field("lot_step", pa.float64(), nullable=False),
        pa.field("currency", pa.string(), nullable=False),
        pa.field("session_calendar", pa.string(), nullable=False),
        pa.field("valid_from", _UTC_NS, nullable=False),
        pa.field("valid_to", _UTC_NS, nullable=True),
    ]
)


TRADE_SCHEMA = pa.schema(
    [
        pa.field("event_time", _UTC_NS, nullable=False),
        pa.field("available_at", _UTC_NS, nullable=False),
        pa.field("source_sequence", pa.int64(), nullable=False),
        pa.field("instrument_id", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("schema_id", pa.string(), nullable=False),
        pa.field("price", pa.float64(), nullable=False),
        pa.field("size", pa.float64(), nullable=True),
        pa.field("source_flags", pa.int32(), nullable=False),
    ]
)

CALENDAR_SCHEMA = pa.schema(
    [
        pa.field("instrument_id", pa.string(), nullable=False),
        pa.field("session_name", pa.string(), nullable=False),
        pa.field("open_time", _UTC_NS, nullable=False),
        pa.field("close_time", _UTC_NS, nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("schema_id", pa.string(), nullable=False),
    ]
)


@dataclass(frozen=True, slots=True)
class RowProblem:
    """One failing row: its index in the table and the rule it broke."""

    row: int
    reason: str


def _column(table: pa.Table, name: str) -> np.ndarray[Any, Any]:
    """Return a table column as a NumPy array.

    Args:
        table: Arrow table to read from.
        name: Column name.

    Returns:
        NumPy array of the column values; nulls use the NumPy null representation.
    """
    return np.asarray(table.column(name).to_numpy(zero_copy_only=False))


def _as_ns(table: pa.Table, name: str) -> np.ndarray[Any, Any]:
    """Return a timestamp column as int64 nanoseconds since the epoch, UTC.

    Args:
        table: Arrow table to read from.
        name: Timestamp column name.

    Returns:
        int64 NumPy array of nanoseconds.
    """
    return np.asarray(
        table.column(name).cast(pa.int64()).to_numpy(zero_copy_only=False), dtype=np.int64
    )


def validate_quotes(table: pa.Table) -> list[RowProblem]:
    """Return rule violations for a normalized quote table.

    Args:
        table: Normalized quote table with the QUOTE_SCHEMA columns.

    Returns:
        Every violation with its row index and reason; an empty list when the table is valid.
    """
    problems: list[RowProblem] = []
    event_ns = _as_ns(table, "event_time")
    avail_ns = _as_ns(table, "available_at")
    seq = _as_ns(table, "source_sequence")
    instr = _column(table, "instrument_id")
    bid = table.column("bid").to_numpy(zero_copy_only=False)
    ask = table.column("ask").to_numpy(zero_copy_only=False)
    bid_null = table.column("bid").is_null().to_numpy(zero_copy_only=False)
    ask_null = table.column("ask").is_null().to_numpy(zero_copy_only=False)

    seen: dict[tuple[str, int], int] = {}
    dupes: set[tuple[str, int]] = set()
    for i, key in enumerate(zip(instr, seq.tolist(), strict=True)):
        if key in seen:
            dupes.add(key)
        seen.setdefault(key, i)
    for i in range(table.num_rows):
        if avail_ns[i] < event_ns[i]:
            problems.append(RowProblem(i, "available_at precedes event_time"))
        if (instr[i], int(seq[i])) in dupes:
            problems.append(RowProblem(i, "duplicate (instrument, source_sequence)"))
        for label, value, is_null in (("bid", bid[i], bid_null[i]), ("ask", ask[i], ask_null[i])):
            if not is_null and (not np.isfinite(value) or value <= 0):
                problems.append(RowProblem(i, f"{label} must be finite and positive"))
        if not bid_null[i] and not ask_null[i] and bid[i] > ask[i]:
            problems.append(RowProblem(i, "bid exceeds ask"))
    return problems


def validate_bars(table: pa.Table) -> list[RowProblem]:
    """Return rule violations for a normalized OHLC bar table.

    Args:
        table: Normalized bar table with the BAR_SCHEMA columns.

    Returns:
        Every violation with its row index and reason; an empty list when the table is valid.
    """
    problems: list[RowProblem] = []
    event_ns = _as_ns(table, "event_time")
    close_ns = _as_ns(table, "close_time")
    avail_ns = _as_ns(table, "available_at")
    instr = _column(table, "instrument_id")
    o = _column(table, "open")
    h = _column(table, "high")
    lo = _column(table, "low")
    c = _column(table, "close")
    counts: dict[tuple[str, int], int] = {}
    for key in zip(instr, event_ns.tolist(), strict=True):
        counts[key] = counts.get(key, 0) + 1
    for i in range(table.num_rows):
        if counts[(instr[i], int(event_ns[i]))] > 1:
            problems.append(RowProblem(i, "duplicate bar open time for instrument"))
        if close_ns[i] <= event_ns[i]:
            problems.append(RowProblem(i, "close_time must follow event_time"))
        if avail_ns[i] < close_ns[i]:
            problems.append(RowProblem(i, "available_at precedes close_time (incomplete bar)"))
        if not all(np.isfinite(v) and v > 0 for v in (o[i], h[i], lo[i], c[i])):
            problems.append(RowProblem(i, "OHLC must be finite and positive"))
            continue
        if h[i] < max(o[i], c[i], lo[i]) or lo[i] > min(o[i], c[i], h[i]):
            problems.append(RowProblem(i, "OHLC bounds violated"))
    return problems


def validate_trades(table: pa.Table) -> list[RowProblem]:
    """Return rule violations for a normalized trade table.

    Args:
        table: Normalized trade table with the TRADE_SCHEMA columns.

    Returns:
        Every violation with its row index and reason; an empty list when the table is valid.
    """
    problems: list[RowProblem] = []
    event_ns = _as_ns(table, "event_time")
    avail_ns = _as_ns(table, "available_at")
    seq = _as_ns(table, "source_sequence")
    instr = _column(table, "instrument_id")
    price = _column(table, "price")
    size = table.column("size").to_numpy(zero_copy_only=False)
    size_null = table.column("size").is_null().to_numpy(zero_copy_only=False)
    keys = list(zip(instr, seq.tolist(), strict=True))
    counts = Counter(keys)
    for i in range(table.num_rows):
        if avail_ns[i] < event_ns[i]:
            problems.append(RowProblem(i, "available_at precedes event_time"))
        if counts[keys[i]] > 1:
            problems.append(RowProblem(i, "duplicate (instrument, source_sequence)"))
        if not (np.isfinite(price[i]) and price[i] > 0):
            problems.append(RowProblem(i, "price must be finite and positive"))
        if not size_null[i] and not (np.isfinite(size[i]) and size[i] >= 0):
            problems.append(RowProblem(i, "size must be finite and non-negative"))
    return problems


def validate_calendar(table: pa.Table) -> list[RowProblem]:
    """Return rule violations for a session calendar table.

    Sessions of one instrument must not overlap. Sessions of different instruments may.

    Args:
        table: Session calendar table with the CALENDAR_SCHEMA columns.

    Returns:
        Every violation with its row index and reason; an empty list when the table is valid.
    """
    problems: list[RowProblem] = []
    open_ns = _as_ns(table, "open_time")
    close_ns = _as_ns(table, "close_time")
    instr = _column(table, "instrument_id")
    for i in range(table.num_rows):
        if close_ns[i] <= open_ns[i]:
            problems.append(RowProblem(i, "close_time must follow open_time"))
    by_instrument: dict[str, list[int]] = {}
    for i in range(table.num_rows):
        if close_ns[i] > open_ns[i]:
            by_instrument.setdefault(str(instr[i]), []).append(i)
    for rows in by_instrument.values():
        rows.sort(key=lambda i: (int(open_ns[i]), int(close_ns[i]), i))
        latest_close: int | None = None
        for i in rows:
            if latest_close is not None and open_ns[i] < latest_close:
                problems.append(
                    RowProblem(i, "session overlaps a previous session of the same instrument")
                )
            latest_close = (
                int(close_ns[i]) if latest_close is None else max(latest_close, int(close_ns[i]))
            )
    return problems


def quarantine_mask(problems: list[RowProblem], num_rows: int) -> np.ndarray[Any, Any]:
    """Return a boolean mask that is True for every row with at least one problem.

    Args:
        problems: Violations returned by a validator.
        num_rows: Number of rows in the validated table.

    Returns:
        Boolean mask of length num_rows.
    """
    mask: np.ndarray[Any, Any] = np.zeros(num_rows, dtype=bool)
    for problem in problems:
        mask[problem.row] = True
    return mask


SOURCE_CLOCK = "Europe/Helsinki"
"""Declared source clock of MT5 chart exports (``config/base/default.yaml``: ``timestamp_clock``)."""

_TIMEFRAME_MINUTES = {
    "M1": 1,
    "M3": 3,
    "M5": 5,
    "M10": 10,
    "M15": 15,
    "M30": 30,
    "H1": 60,
    "H4": 240,
    "D1": 1440,
}


def mt5_export_to_bars(
    frame: pd.DataFrame, *, instrument_id: str, timeframe: str, source_id: str = "mt5-export"
) -> tuple[pa.Table, list[RowProblem]]:
    """Convert an MT5 chart export frame to normalized UTC bars.

    The export's ``<DATE>`` and ``<TIME>`` are Helsinki wall-clock labels stamped at the bar open.
    Local times that repeat (DST fall-back) or do not exist (spring-forward) cannot be mapped to a
    single UTC instant, so their rows are reported as problems and left out of the table.

    Args:
        frame: Export rows with ``DATE``, ``TIME``, ``OPEN``, ``HIGH``, ``LOW``, ``CLOSE`` and
            ``TICKVOL`` columns, in file order.
        instrument_id: Instrument identity written to every row.
        timeframe: Native MT5 timeframe label such as ``M1`` or ``H1``.
        source_id: Source identity written to every row.

    Returns:
        The converted bar table, with every row that failed validation removed, and the problems.
        ``RowProblem.row`` indexes ``frame``; callers persist the problems as the quarantine record.
    """
    minutes = _TIMEFRAME_MINUTES.get(timeframe)
    if minutes is None:
        raise ValueError(f"unsupported native timeframe {timeframe!r}")
    local = pd.to_datetime(
        frame["DATE"].astype(str) + " " + frame["TIME"].astype(str), format="%Y.%m.%d %H:%M:%S"
    )
    strict = local.dt.tz_localize(SOURCE_CLOCK, ambiguous="NaT", nonexistent="NaT")
    lenient = local.dt.tz_localize(SOURCE_CLOCK, ambiguous=True, nonexistent="NaT")
    problems: list[RowProblem] = []
    for position in range(len(frame)):
        if pd.isna(strict.iloc[position]):
            reason = (
                "nonexistent local time (DST spring-forward)"
                if pd.isna(lenient.iloc[position])
                else "ambiguous local time (DST fall-back)"
            )
            problems.append(RowProblem(position, reason))
    valid = strict.notna().to_numpy()
    keep = np.flatnonzero(valid).tolist()
    open_ns = pd.DatetimeIndex(strict[valid].dt.tz_convert("UTC"))
    close_ns = open_ns + pd.Timedelta(minutes=minutes)
    selected = frame.iloc[keep]
    rows = len(keep)
    table = pa.table(
        {
            "event_time": pa.array(open_ns.to_numpy(), type=pa.timestamp("ns", tz="UTC")),
            "close_time": pa.array(close_ns.to_numpy(), type=pa.timestamp("ns", tz="UTC")),
            "available_at": pa.array(close_ns.to_numpy(), type=pa.timestamp("ns", tz="UTC")),
            "source_sequence": pa.array(np.asarray(keep, dtype=np.int64), type=pa.int64()),
            "instrument_id": pa.array([instrument_id] * rows, type=pa.string()),
            "source_id": pa.array([source_id] * rows, type=pa.string()),
            "schema_id": pa.array([SCHEMA_VERSION] * rows, type=pa.string()),
            "open": pa.array(selected["OPEN"].to_numpy(dtype=np.float64), type=pa.float64()),
            "high": pa.array(selected["HIGH"].to_numpy(dtype=np.float64), type=pa.float64()),
            "low": pa.array(selected["LOW"].to_numpy(dtype=np.float64), type=pa.float64()),
            "close": pa.array(selected["CLOSE"].to_numpy(dtype=np.float64), type=pa.float64()),
            "volume": pa.array(selected["TICKVOL"].to_numpy(dtype=np.float64), type=pa.float64()),
        },
        schema=BAR_SCHEMA,
    )
    bar_problems = validate_bars(table)
    for problem in bar_problems:
        problems.append(RowProblem(keep[problem.row], problem.reason))
    if bar_problems:
        bad = np.zeros(table.num_rows, dtype=bool)
        for problem in bar_problems:
            bad[problem.row] = True
        table = table.filter(pa.array(~bad))
    return table, sorted(problems, key=lambda p: p.row)
