"""Physical Arrow/Parquet schemas and validators for normalized market data (DATA-SCHEMAS).

The semantics are declared by :class:`market_data.contracts.MarketEventSchema`; this module adds
the physical types. Times are UTC ``timestamp[ns]`` with an explicit source clock, an availability
time, and a source sequence used as the stable tie-breaker. Missing values are null, never
sentinel zeros. Validators return the failing row indices with reasons so that invalid records can
be quarantined rather than silently dropped.

Validators first reject a table whose schema id they do not accept (a schema error, raised), then
report row defects. A null in a non-nullable field is a row defect; the row is not checked further.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]

SCHEMA_VERSION = "market-event.v1"
"""Schema id of the bar and trade layouts, and of the legacy quote layout (see LEGACY_QUOTE_SCHEMA)."""

QUOTE_EVENT_SCHEMA_ID = "quote-event.v1"
"""Schema id of the quote layout, which carries an explicit per-row ``origin`` tag."""

CALENDAR_SCHEMA_ID = "session-calendar.v1"
INSTRUMENT_SCHEMA_ID = "instrument-metadata.v1"
NORMALIZED_EVENT_SCHEMA_ID = "normalized-event.v1"
FEATURE_ROW_SCHEMA_ID = "feature-row.v1"
BAR_REVISED_SCHEMA_ID = "market-event.v2"
"""Bars with an integer correction ``revision``; produced only by :mod:`market_data.schema_migration`."""

QUOTE_ORIGINS = frozenset({"observed", "ohlc_synthetic"})
"""Every quote row is tagged. ``observed`` came from the source; ``ohlc_synthetic`` was derived from bars."""

_UTC_NS = pa.timestamp("ns", tz="UTC")

QUOTE_SCHEMA = pa.schema(
    [
        pa.field("event_time", _UTC_NS, nullable=False),
        pa.field("available_at", _UTC_NS, nullable=False),
        pa.field("source_sequence", pa.int64(), nullable=False),
        pa.field("instrument_id", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("schema_id", pa.string(), nullable=False),
        pa.field("origin", pa.string(), nullable=False),
        pa.field("bid", pa.float64(), nullable=True),
        pa.field("ask", pa.float64(), nullable=True),
        pa.field("bid_size", pa.float64(), nullable=True),
        pa.field("ask_size", pa.float64(), nullable=True),
        pa.field("source_flags", pa.int32(), nullable=False),
    ]
)

LEGACY_QUOTE_SCHEMA = pa.schema([field for field in QUOTE_SCHEMA if field.name != "origin"])
"""The untagged quote layout written under ``market-event.v1``. Read only through the migration."""

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
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("schema_id", pa.string(), nullable=False),
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

CALENDAR_KINDS = frozenset({"trading", "early_close", "closed"})

CALENDAR_SCHEMA = pa.schema(
    [
        pa.field("instrument_id", pa.string(), nullable=False),
        pa.field("session_open", _UTC_NS, nullable=False),
        pa.field("session_close", _UTC_NS, nullable=False),
        pa.field("session_kind", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("schema_id", pa.string(), nullable=False),
    ]
)

BAR_REVISED_SCHEMA = pa.schema([*BAR_SCHEMA, pa.field("revision", pa.int64(), nullable=False)])

SUPPORTED_SCHEMA_IDS = frozenset(
    {
        SCHEMA_VERSION,
        QUOTE_EVENT_SCHEMA_ID,
        CALENDAR_SCHEMA_ID,
        INSTRUMENT_SCHEMA_ID,
        NORMALIZED_EVENT_SCHEMA_ID,
        FEATURE_ROW_SCHEMA_ID,
        BAR_REVISED_SCHEMA_ID,
    }
)
"""Schema identities this reader accepts. Any other id fails closed; see the README migration policy."""

BAR_SCHEMA_IDS = frozenset({SCHEMA_VERSION, BAR_REVISED_SCHEMA_ID})

ORDER_REASON = "event_time precedes the previous row in source_sequence order"

TIMESTAMP_UNITS_PER_NS = {"s": 1_000_000_000, "ms": 1_000_000, "us": 1_000, "ns": 1}
PLAUSIBLE_MIN_NS = int(datetime(1990, 1, 1, tzinfo=UTC).timestamp()) * 1_000_000_000
PLAUSIBLE_MAX_NS = int(datetime(2100, 1, 1, tzinfo=UTC).timestamp()) * 1_000_000_000


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
    """Return a timestamp or int64 column as int64 values, with nulls set to 0.

    Null rows are excluded by the caller through their null mask; the 0 is never reported.

    Args:
        table: Arrow table to read from.
        name: Timestamp column name.

    Returns:
        int64 NumPy array of nanoseconds (or of the column's integer values).
    """
    filled = table.column(name).cast(pa.int64()).fill_null(0)
    return np.asarray(filled.to_numpy(zero_copy_only=False), dtype=np.int64)


def _floats(table: pa.Table, name: str) -> np.ndarray[Any, Any]:
    """Return a numeric column as float64, with nulls as NaN.

    Args:
        table: Arrow table to read from.
        name: Column name.

    Returns:
        float64 array; a null is NaN and is always tested with the null mask first.
    """
    return np.asarray(table.column(name).to_numpy(zero_copy_only=False), dtype=np.float64)


def _is_null(table: pa.Table, name: str) -> np.ndarray[Any, Any]:
    """Return the null mask of one column.

    Args:
        table: Arrow table to read from.
        name: Column name.

    Returns:
        Boolean array, True where the value is null.
    """
    return np.asarray(table.column(name).is_null().to_numpy(zero_copy_only=False), dtype=bool)


def _positive(values: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """Return True where a value is finite and strictly positive.

    Args:
        values: Float values; NaN is not positive.

    Returns:
        Boolean array of the same length.
    """
    return np.asarray(np.isfinite(values) & (values > 0), dtype=bool)


def _nonnegative(values: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """Return True where a value is finite and not negative.

    Args:
        values: Float values; NaN is not non-negative.

    Returns:
        Boolean array of the same length.
    """
    return np.asarray(np.isfinite(values) & (values >= 0), dtype=bool)


def _rows(mask: np.ndarray[Any, Any], reason: str) -> list[RowProblem]:
    """Return one problem per True row of a mask.

    Args:
        mask: Boolean array over the table rows.
        reason: Reason recorded for every flagged row.

    Returns:
        The flagged rows, in row order.
    """
    return [RowProblem(int(i), reason) for i in np.flatnonzero(mask)]


def _sorted(problems: list[RowProblem]) -> list[RowProblem]:
    """Return problems in row order, keeping the rule order within a row.

    Args:
        problems: Problems in the order the rules produced them.

    Returns:
        The same problems, stably sorted by row index.
    """
    return sorted(problems, key=lambda p: p.row)


def _require_columns(table: pa.Table, schema: pa.Schema) -> None:
    """Refuse a table that lacks a column the validator reads.

    Args:
        table: Table to check.
        schema: Schema whose column names must be present.

    Raises:
        ValueError: If any column of ``schema`` is missing.
    """
    missing = [name for name in schema.names if name not in table.column_names]
    if missing:
        raise ValueError(f"table is missing columns {missing}")


def _require_accepted_ids(table: pa.Table, accepted: frozenset[str]) -> None:
    """Refuse a non-empty table whose schema id is not accepted by the validator.

    Args:
        table: Table to check. An empty table has no id to check and passes.
        accepted: Schema ids the validator accepts.

    Raises:
        ValueError: If the table mixes ids or carries an id outside ``accepted``.
    """
    if "schema_id" not in table.column_names:
        raise ValueError("table is missing columns ['schema_id']")
    if table.num_rows:
        require_schema_id(table, accepted=accepted)


def _null_problems(
    table: pa.Table, schema: pa.Schema
) -> tuple[list[RowProblem], np.ndarray[Any, Any]]:
    """Flag every null in a non-nullable field of ``schema``.

    Args:
        table: Table to check.
        schema: Schema whose nullability declares which fields may not be null.

    Returns:
        The null problems, and a mask of rows with at least one null in a non-nullable field.
        Those rows must be skipped by the other rules.
    """
    bad = np.zeros(table.num_rows, dtype=bool)
    problems: list[RowProblem] = []
    for field in schema:
        if field.nullable:
            continue
        null = _is_null(table, field.name)
        bad |= null
        problems.extend(_rows(null, f"null in non-nullable field {field.name}"))
    return problems, bad


def _duplicate_problems(
    columns: list[np.ndarray[Any, Any]], skip: np.ndarray[Any, Any], reason: str
) -> list[RowProblem]:
    """Flag every occurrence of a repeated key, not only the second one.

    Args:
        columns: Key columns; a repeated key is a repeated tuple across them.
        skip: Rows to leave out (null rows).
        reason: Reason recorded for every occurrence.

    Returns:
        One problem per row whose key occurs more than once among the checked rows.
    """
    frame = pd.DataFrame({str(i): column for i, column in enumerate(columns)})
    frame = frame.loc[~skip]
    duplicated = frame.duplicated(keep=False).to_numpy(dtype=bool)
    return [RowProblem(int(i), reason) for i in frame.index.to_numpy()[duplicated]]


def _order_problems(
    instrument: np.ndarray[Any, Any],
    sequence: np.ndarray[Any, Any],
    event_ns: np.ndarray[Any, Any],
    skip: np.ndarray[Any, Any],
) -> list[RowProblem]:
    """Flag each row whose event time precedes the row before it in source sequence.

    Ordering is checked per instrument. The source sequence is the tie-breaker, so equal event
    times are allowed and a row is only flagged for moving backwards in time.

    Args:
        instrument: Instrument identity of each row.
        sequence: Source sequence of each row.
        event_ns: Event time of each row in nanoseconds.
        skip: Rows to leave out (null rows).

    Returns:
        One problem per row that moves backwards in time.
    """
    live = np.flatnonzero(~skip)
    if live.size < 2:
        return []
    codes = np.asarray(pd.factorize(instrument)[0], dtype=np.int64)
    perm = live[np.lexsort((sequence[live], codes[live]))]
    same = codes[perm][1:] == codes[perm][:-1]
    backwards = same & (event_ns[perm][1:] < event_ns[perm][:-1])
    return [RowProblem(int(i), ORDER_REASON) for i in perm[1:][backwards]]


def validate_quotes(table: pa.Table) -> list[RowProblem]:
    """Return rule violations for a normalized quote table.

    Every row must carry an explicit ``origin`` (``observed`` or ``ohlc_synthetic``). A one-sided
    quote keeps an explicit null on the missing side. A crossed quote is a violation.

    Args:
        table: Normalized quote table with the QUOTE_SCHEMA columns and schema id
            ``quote-event.v1``.

    Returns:
        Every violation with its row index and reason; an empty list when the table is valid.

    Raises:
        ValueError: If a column is missing or the schema id is not ``quote-event.v1``. A legacy
            ``market-event.v1`` quote table must first go through the quote migration.
    """
    _require_accepted_ids(table, frozenset({QUOTE_EVENT_SCHEMA_ID}))
    _require_columns(table, QUOTE_SCHEMA)
    problems, bad = _null_problems(table, QUOTE_SCHEMA)
    live = ~bad
    event = _as_ns(table, "event_time")
    avail = _as_ns(table, "available_at")
    sequence = _as_ns(table, "source_sequence")
    instrument = _column(table, "instrument_id")
    origin = _column(table, "origin")
    origin_ok = np.array([value in QUOTE_ORIGINS for value in origin], dtype=bool)
    bid = _floats(table, "bid")
    ask = _floats(table, "ask")
    has_bid = ~_is_null(table, "bid")
    has_ask = ~_is_null(table, "ask")

    problems += _rows(
        live & ~origin_ok, "origin must be 'observed' or 'ohlc_synthetic' (untagged quote)"
    )
    problems += _rows(live & (avail < event), "available_at precedes event_time")
    problems += _rows(live & has_bid & ~_positive(bid), "bid must be finite and positive")
    problems += _rows(live & has_ask & ~_positive(ask), "ask must be finite and positive")
    problems += _rows(live & has_bid & has_ask & (bid > ask), "bid exceeds ask")
    for name in ("bid_size", "ask_size"):
        size = _floats(table, name)
        problems += _rows(
            live & ~_is_null(table, name) & ~_nonnegative(size),
            f"{name} must be finite and non-negative",
        )
    problems += _duplicate_problems(
        [instrument, sequence], bad, "duplicate (instrument, source_sequence)"
    )
    problems += _order_problems(instrument, sequence, event, bad)
    return _sorted(problems)


def validate_bars(table: pa.Table) -> list[RowProblem]:
    """Return rule violations for a normalized OHLC bar table.

    A bar's ``event_time`` is its open. ``close_time`` must follow it, and ``available_at`` must not
    precede the close. Several rows with one open time are a duplicate, and each one is flagged.

    Args:
        table: Normalized bar table with the BAR_SCHEMA columns and schema id ``market-event.v1``
            or ``market-event.v2``.

    Returns:
        Every violation with its row index and reason; an empty list when the table is valid.

    Raises:
        ValueError: If a column is missing or the schema id is neither bar id.
    """
    _require_accepted_ids(table, BAR_SCHEMA_IDS)
    _require_columns(table, BAR_SCHEMA)
    problems, bad = _null_problems(table, BAR_SCHEMA)
    live = ~bad
    event = _as_ns(table, "event_time")
    close = _as_ns(table, "close_time")
    avail = _as_ns(table, "available_at")
    sequence = _as_ns(table, "source_sequence")
    instrument = _column(table, "instrument_id")
    o, h, lo, c = (_floats(table, name) for name in ("open", "high", "low", "close"))
    problems += _duplicate_problems(
        [instrument, event], bad, "duplicate bar open time for instrument"
    )
    problems += _rows(live & (close <= event), "close_time must follow event_time")
    problems += _rows(live & (avail < close), "available_at precedes close_time (incomplete bar)")
    finite = _positive(o) & _positive(h) & _positive(lo) & _positive(c)
    problems += _rows(live & ~finite, "OHLC must be finite and positive")
    checked = live & finite
    outside = (h < np.maximum(np.maximum(o, c), lo)) | (lo > np.minimum(np.minimum(o, c), h))
    problems += _rows(checked & outside, "OHLC bounds violated")
    problems += _rows(
        live & ~_is_null(table, "volume") & ~_nonnegative(_floats(table, "volume")),
        "volume must be finite and non-negative",
    )
    problems += _order_problems(instrument, sequence, event, bad)
    return _sorted(problems)


def validate_trades(table: pa.Table) -> list[RowProblem]:
    """Return rule violations for a normalized trade table.

    Args:
        table: Normalized trade table with the TRADE_SCHEMA columns and schema id ``market-event.v1``.

    Returns:
        Every violation with its row index and reason; an empty list when the table is valid.

    Raises:
        ValueError: If a column is missing or the schema id is not ``market-event.v1``.
    """
    _require_accepted_ids(table, frozenset({SCHEMA_VERSION}))
    _require_columns(table, TRADE_SCHEMA)
    problems, bad = _null_problems(table, TRADE_SCHEMA)
    live = ~bad
    event = _as_ns(table, "event_time")
    avail = _as_ns(table, "available_at")
    sequence = _as_ns(table, "source_sequence")
    instrument = _column(table, "instrument_id")
    price = _floats(table, "price")
    problems += _rows(live & (avail < event), "available_at precedes event_time")
    problems += _duplicate_problems(
        [instrument, sequence], bad, "duplicate (instrument, source_sequence)"
    )
    problems += _rows(live & ~_positive(price), "price must be finite and positive")
    problems += _rows(
        live & ~_is_null(table, "size") & ~_nonnegative(_floats(table, "size")),
        "size must be finite and non-negative",
    )
    problems += _order_problems(instrument, sequence, event, bad)
    return _sorted(problems)


def validate_instruments(table: pa.Table) -> list[RowProblem]:
    """Return rule violations for instrument metadata.

    Contract size, price tick and lot step must be finite and positive. The currency must be a
    three-letter upper-case code. Validity intervals must be non-empty and must not overlap for one
    instrument. An open-ended interval has ``valid_to`` null.

    Args:
        table: Instrument table with the INSTRUMENT_SCHEMA columns and schema id
            ``instrument-metadata.v1``.

    Returns:
        Every violation with its row index and reason; an empty list when the table is valid.

    Raises:
        ValueError: If a column is missing or the schema id is not ``instrument-metadata.v1``.
    """
    _require_accepted_ids(table, frozenset({INSTRUMENT_SCHEMA_ID}))
    _require_columns(table, INSTRUMENT_SCHEMA)
    problems, bad = _null_problems(table, INSTRUMENT_SCHEMA)
    live = ~bad
    for name in ("contract_size", "price_tick", "lot_step"):
        problems += _rows(
            live & ~_positive(_floats(table, name)), f"{name} must be finite and positive"
        )
    currency = _column(table, "currency")
    currency_ok = np.array(
        [
            isinstance(c, str) and len(c) == 3 and c.isascii() and c.isalpha() and c.isupper()
            for c in currency
        ],
        dtype=bool,
    )
    problems += _rows(live & ~currency_ok, "currency must be a three-letter upper-case code")
    calendar = _column(table, "session_calendar")
    calendar_ok = np.array([isinstance(s, str) and s.strip() != "" for s in calendar], dtype=bool)
    problems += _rows(live & ~calendar_ok, "session_calendar is required")
    start = _as_ns(table, "valid_from")
    has_end = ~_is_null(table, "valid_to")
    end = np.where(has_end, _as_ns(table, "valid_to"), np.iinfo(np.int64).max)
    problems += _rows(live & has_end & (end <= start), "valid_to must follow valid_from")
    instrument = _column(table, "instrument_id")
    order = np.lexsort((start, pd.factorize(instrument)[0]))
    order = order[live[order]]
    codes = pd.factorize(instrument)[0]
    for a, b in zip(order[:-1], order[1:], strict=False):
        if codes[a] == codes[b] and start[b] < end[a]:
            problems.append(RowProblem(int(a), "validity interval overlaps the next interval"))
            problems.append(RowProblem(int(b), "validity interval overlaps the previous interval"))
    return _sorted(problems)


def validate_calendar(table: pa.Table) -> list[RowProblem]:
    """Return rule violations for a session calendar table.

    Sessions are half-open intervals ``[session_open, session_close)``. Overlapping sessions for
    the same instrument are reported on every involved row.

    Args:
        table: Calendar table with the CALENDAR_SCHEMA columns and schema id ``session-calendar.v1``.

    Returns:
        Every violation with its row index and reason; an empty list when the table is valid.

    Raises:
        ValueError: If a column is missing or the schema id is not ``session-calendar.v1``.
    """
    _require_accepted_ids(table, frozenset({CALENDAR_SCHEMA_ID}))
    _require_columns(table, CALENDAR_SCHEMA)
    problems, bad = _null_problems(table, CALENDAR_SCHEMA)
    open_ns = _as_ns(table, "session_open")
    close_ns = _as_ns(table, "session_close")
    instr = _column(table, "instrument_id")
    kind = _column(table, "session_kind")
    for i in range(table.num_rows):
        if bad[i]:
            continue
        if close_ns[i] <= open_ns[i]:
            problems.append(RowProblem(i, "session_close must follow session_open"))
        if kind[i] not in CALENDAR_KINDS:
            problems.append(RowProblem(i, f"unknown session_kind {kind[i]!r}"))
    by_instrument: dict[str, list[int]] = {}
    for i in range(table.num_rows):
        if not bad[i]:
            by_instrument.setdefault(str(instr[i]), []).append(i)
    for rows in by_instrument.values():
        ordered = sorted(rows, key=lambda r: (open_ns[r], close_ns[r]))
        for a, b in zip(ordered, ordered[1:], strict=False):
            if open_ns[b] < close_ns[a]:
                problems.append(RowProblem(a, "session overlaps the next session"))
                problems.append(RowProblem(b, "session overlaps the previous session"))
    return _sorted(problems)


def epoch_to_utc_ns(values: np.ndarray[Any, Any], unit: str) -> np.ndarray[Any, Any]:
    """Convert integer epoch values with a declared unit to UTC nanoseconds, refusing implausible ones.

    A source that writes milliseconds read as nanoseconds gives 1970 dates, which a silent cast
    accepts. Values outside 1990-01-01 to 2100-01-01 UTC are therefore refused. This is a guard
    against a wrong declared unit, not a proof that the unit is right.

    Args:
        values: Integer epoch values from the source.
        unit: Declared unit: ``s``, ``ms``, ``us`` or ``ns``.

    Returns:
        int64 nanoseconds since the epoch, UTC.

    Raises:
        ValueError: If the unit is unknown or a value falls outside the plausible range.
    """
    if unit not in TIMESTAMP_UNITS_PER_NS:
        raise ValueError(
            f"unknown timestamp unit {unit!r}; expected one of {sorted(TIMESTAMP_UNITS_PER_NS)}"
        )
    factor = TIMESTAMP_UNITS_PER_NS[unit]
    raw = np.asarray(values, dtype=np.int64)
    if raw.size == 0:
        return raw
    lower = PLAUSIBLE_MIN_NS // factor
    upper = PLAUSIBLE_MAX_NS // factor
    if int(raw.min()) < lower or int(raw.max()) >= upper:
        raise ValueError(
            f"values outside 1990-2100 UTC when read as {unit}; the declared unit is probably wrong"
        )
    return raw * factor


def require_schema_id(table: pa.Table, accepted: frozenset[str] = SUPPORTED_SCHEMA_IDS) -> str:
    """Return the single schema id of a table, failing closed on unknown, mixed or unaccepted ids.

    Args:
        table: Normalized table with a ``schema_id`` column.
        accepted: Ids this caller accepts. Defaults to every id this package supports; a narrower
            set lets a reader refuse a newer id it cannot interpret.

    Returns:
        The one schema id carried by every row.

    Raises:
        ValueError: If the table is empty, mixes ids, or carries an id outside ``accepted``.
    """
    ids = set(table.column("schema_id").to_pylist())
    if len(ids) != 1:
        raise ValueError(f"table must carry exactly one schema_id, found {sorted(ids, key=str)!r}")
    (schema_id,) = ids
    if schema_id not in SUPPORTED_SCHEMA_IDS or schema_id not in accepted:
        raise ValueError(f"unsupported schema_id {schema_id!r}; supported {sorted(accepted)!r}")
    return str(schema_id)


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
