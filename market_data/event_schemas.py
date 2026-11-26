"""Normalized event and feature-row Arrow schemas with validators (DATA-SCHEMAS).

A normalized event is one row per quote, trade or completed bar, with a common header
(``event_time``, ``available_at``, ``source_sequence``, identities) and a small typed payload.
The payload is positional by ``event_type``, documented in :data:`PAYLOAD_FIELDS`, so that one
table can carry all three kinds without sentinel values: a field that does not apply is null.

A feature row is one decision-clock row of a named feature set. Its values are a list of nullable
float64 in the order declared by the feature-set manifest. A null element means missing (warm-up,
no data), never a sentinel zero. Feature rows must not use information after their event time.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]

from market_data.arrow_schemas import (
    FEATURE_ROW_SCHEMA_ID,
    NORMALIZED_EVENT_SCHEMA_ID,
    RowProblem,
    _as_ns,
    _column,
)

_UTC_NS = pa.timestamp("ns", tz="UTC")

EVENT_TYPES = frozenset({"quote", "trade", "bar"})

PAYLOAD_FIELDS: dict[str, tuple[str, ...]] = {
    # quote: value_a = bid, value_b = ask; size unused. A one-sided quote stays in the quote table
    # (QUOTE_SCHEMA), not in normalized events, so a normalized quote always has both sides.
    "quote": ("value_a", "value_b"),
    # trade: value_a = price, size = traded size when the source provides it.
    "trade": ("value_a",),
    # bar: value_a..value_d = open, high, low, close; size = volume when the source provides it.
    "bar": ("value_a", "value_b", "value_c", "value_d"),
}

NORMALIZED_EVENT_SCHEMA = pa.schema(
    [
        pa.field("event_time", _UTC_NS, nullable=False),
        pa.field("available_at", _UTC_NS, nullable=False),
        pa.field("source_sequence", pa.int64(), nullable=False),
        pa.field("instrument_id", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("schema_id", pa.string(), nullable=False),
        pa.field("event_type", pa.string(), nullable=False),
        pa.field("value_a", pa.float64(), nullable=True),
        pa.field("value_b", pa.float64(), nullable=True),
        pa.field("value_c", pa.float64(), nullable=True),
        pa.field("value_d", pa.float64(), nullable=True),
        pa.field("size", pa.float64(), nullable=True),
    ]
)

FEATURE_ROW_SCHEMA = pa.schema(
    [
        pa.field("event_time", _UTC_NS, nullable=False),
        pa.field("available_at", _UTC_NS, nullable=False),
        pa.field("instrument_id", pa.string(), nullable=False),
        pa.field("feature_set_id", pa.string(), nullable=False),
        pa.field("feature_version", pa.string(), nullable=False),
        pa.field("content_hash", pa.string(), nullable=False),
        pa.field("schema_id", pa.string(), nullable=False),
        pa.field("session_eligible", pa.bool_(), nullable=False),
        pa.field("values", pa.list_(pa.field("item", pa.float64(), nullable=True)), nullable=False),
    ]
)


def validate_normalized_events(table: pa.Table) -> list[RowProblem]:
    """Return rule violations for a normalized event table.

    Args:
        table: Table with the NORMALIZED_EVENT_SCHEMA columns.

    Returns:
        Every violation with its row index and reason; an empty list when the table is valid.
    """
    problems: list[RowProblem] = []
    event_ns = _as_ns(table, "event_time")
    avail_ns = _as_ns(table, "available_at")
    seq = _as_ns(table, "source_sequence")
    instr = _column(table, "instrument_id")
    kinds = table.column("event_type").to_pylist()
    payload = {
        name: table.column(name).to_pylist()
        for name in ("value_a", "value_b", "value_c", "value_d", "size")
    }

    seen: dict[tuple[str, int], int] = {}
    dupes: set[tuple[str, int]] = set()
    for i in range(table.num_rows):
        key = (str(instr[i]), int(seq[i]))
        if key in seen:
            dupes.add(key)
        seen.setdefault(key, i)
    for i in range(table.num_rows):
        if avail_ns[i] < event_ns[i]:
            problems.append(RowProblem(i, "available_at precedes event_time"))
        if (str(instr[i]), int(seq[i])) in dupes:
            problems.append(RowProblem(i, "duplicate (instrument, source_sequence)"))
        kind = kinds[i]
        if kind not in EVENT_TYPES:
            problems.append(RowProblem(i, f"unknown event_type {kind!r}"))
            continue
        required = PAYLOAD_FIELDS[kind]
        for name in ("value_a", "value_b", "value_c", "value_d"):
            value = payload[name][i]
            if name in required and value is None:
                problems.append(RowProblem(i, f"{kind} requires {name}"))
            if name not in required and value is not None:
                problems.append(RowProblem(i, f"{kind} must leave {name} null"))
            if value is not None and not (math.isfinite(value) and value > 0):
                problems.append(RowProblem(i, f"{name} must be finite and positive"))
        size = payload["size"][i]
        if size is not None and not (math.isfinite(size) and size >= 0):
            problems.append(RowProblem(i, "size must be finite and non-negative"))
        if kind == "bar" and all(
            payload[n][i] is not None for n in ("value_a", "value_b", "value_c", "value_d")
        ):
            o, h, lo, c = (payload[n][i] for n in ("value_a", "value_b", "value_c", "value_d"))
            if h < max(o, c, lo) or lo > min(o, c, h):
                problems.append(RowProblem(i, "OHLC bounds violated"))
    return sorted(problems, key=lambda p: p.row)


def validate_feature_rows(table: pa.Table, feature_names: Sequence[str]) -> list[RowProblem]:
    """Return rule violations for a feature-row table of one feature set.

    The width of every row must equal the number of names declared by the feature-set manifest, or
    the table is rejected outright: a width mismatch is a schema error, not a row defect.

    Args:
        table: Table with the FEATURE_ROW_SCHEMA columns.
        feature_names: Output names in manifest order; only their count is checked here.

    Returns:
        Every per-row violation; an empty list when the table is valid.

    Raises:
        ValueError: If a row's value width differs from the declared feature count, or the table
            mixes feature sets or feature versions.
    """
    problems: list[RowProblem] = []
    width = len(feature_names)
    sets = set(table.column("feature_set_id").to_pylist())
    versions = set(table.column("feature_version").to_pylist())
    if len(sets) > 1 or len(versions) > 1:
        raise ValueError(
            "feature-row table must contain one feature_set_id and one feature_version"
        )
    values_column: list[list[Any] | None] = table.column("values").to_pylist()
    for i, row in enumerate(values_column):
        if row is None or len(row) != width:
            raise ValueError(
                f"row {i} has width {None if row is None else len(row)}, expected {width}"
            )

    event_ns = _as_ns(table, "event_time")
    avail_ns = _as_ns(table, "available_at")
    instr = _column(table, "instrument_id")
    schema_ids = table.column("schema_id").to_pylist()
    hashes = table.column("content_hash").to_pylist()

    seen: dict[tuple[str, int], int] = {}
    dupes: set[tuple[str, int]] = set()
    for i in range(table.num_rows):
        key = (str(instr[i]), int(event_ns[i]))
        if key in seen:
            dupes.add(key)
        seen.setdefault(key, i)
    for i in range(table.num_rows):
        if avail_ns[i] > event_ns[i]:
            problems.append(
                RowProblem(i, "feature uses information available after its event_time")
            )
        if (str(instr[i]), int(event_ns[i])) in dupes:
            problems.append(RowProblem(i, "duplicate (instrument, event_time) for feature set"))
        if schema_ids[i] != FEATURE_ROW_SCHEMA_ID:
            problems.append(RowProblem(i, f"schema_id must be {FEATURE_ROW_SCHEMA_ID!r}"))
        if not str(hashes[i]):
            problems.append(RowProblem(i, "content_hash is required"))
        for value in values_column[i] or []:
            if value is not None and not math.isfinite(value):
                problems.append(
                    RowProblem(i, "feature value must be finite or null, not NaN or inf")
                )
                break
    return sorted(problems, key=lambda p: p.row)


def normalized_events_from_arrays(
    *,
    event_time: np.ndarray[Any, Any],
    available_at: np.ndarray[Any, Any],
    source_sequence: np.ndarray[Any, Any],
    instrument_id: str,
    source_id: str,
    event_type: str,
    values: dict[str, np.ndarray[Any, Any]],
) -> pa.Table:
    """Build a normalized event table for one event type from aligned arrays.

    Args:
        event_time: UTC event times as datetime64[ns] or int64 nanoseconds.
        available_at: UTC availability times, same length.
        source_sequence: Stable per-instrument tie-breakers, same length.
        instrument_id: Instrument identity for every row.
        source_id: Source identity for every row.
        event_type: One of EVENT_TYPES.
        values: Payload arrays by field name; fields not listed are null.

    Returns:
        A table with NORMALIZED_EVENT_SCHEMA. Missing payload entries stay null.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event_type {event_type!r}")
    rows = len(event_time)
    columns: dict[str, pa.Array] = {
        "event_time": pa.array(np.asarray(event_time).astype("datetime64[ns]"), type=_UTC_NS),
        "available_at": pa.array(np.asarray(available_at).astype("datetime64[ns]"), type=_UTC_NS),
        "source_sequence": pa.array(np.asarray(source_sequence, dtype=np.int64), type=pa.int64()),
        "instrument_id": pa.array([instrument_id] * rows, type=pa.string()),
        "source_id": pa.array([source_id] * rows, type=pa.string()),
        "schema_id": pa.array([NORMALIZED_EVENT_SCHEMA_ID] * rows, type=pa.string()),
        "event_type": pa.array([event_type] * rows, type=pa.string()),
    }
    for name in ("value_a", "value_b", "value_c", "value_d", "size"):
        if name in values:
            columns[name] = pa.array(
                np.asarray(values[name], dtype=np.float64), type=pa.float64(), from_pandas=False
            )
        else:
            columns[name] = pa.nulls(rows, type=pa.float64())
    return pa.table(columns, schema=NORMALIZED_EVENT_SCHEMA)


__all__ = [
    "EVENT_TYPES",
    "FEATURE_ROW_SCHEMA",
    "NORMALIZED_EVENT_SCHEMA",
    "PAYLOAD_FIELDS",
    "normalized_events_from_arrays",
    "validate_feature_rows",
    "validate_normalized_events",
]
