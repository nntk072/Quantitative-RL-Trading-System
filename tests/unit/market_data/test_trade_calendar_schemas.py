"""DATA-SCHEMAS increment: trade and session-calendar schemas, validators and Parquet round trip.

Only hand-built rows are used. No broker trades or calendars are fabricated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from market_data.arrow_schemas import (
    CALENDAR_SCHEMA,
    QUOTE_SCHEMA,
    SCHEMA_VERSION,
    TRADE_SCHEMA,
    quarantine_mask,
    validate_calendar,
    validate_trades,
)

T0 = datetime(2026, 1, 2, 9, 30, tzinfo=UTC)
T1 = datetime(2026, 1, 2, 9, 31, tzinfo=UTC)
T2 = datetime(2026, 1, 2, 9, 32, tzinfo=UTC)


def _trade(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "event_time": T0,
        "available_at": T0,
        "source_sequence": 1,
        "instrument_id": "US100",
        "source_id": "mt5",
        "schema_id": SCHEMA_VERSION,
        "price": 100.0,
        "size": None,
        "source_flags": 0,
    }
    row.update(overrides)
    return row


def _session(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "instrument_id": "US100",
        "session_name": "regular",
        "open_time": T0,
        "close_time": T2,
        "source_id": "calendar-file",
        "schema_id": SCHEMA_VERSION,
    }
    row.update(overrides)
    return row


def _table(schema: pa.Schema, rows: list[dict[str, object]]) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=schema)


def test_new_schemas_declare_utc_nanosecond_times_and_nullable_size() -> None:
    assert TRADE_SCHEMA.field("event_time").type == pa.timestamp("ns", tz="UTC")
    assert TRADE_SCHEMA.field("available_at").type == pa.timestamp("ns", tz="UTC")
    assert TRADE_SCHEMA.field("price").nullable is False
    assert TRADE_SCHEMA.field("size").nullable is True
    assert CALENDAR_SCHEMA.field("open_time").type == pa.timestamp("ns", tz="UTC")
    assert CALENDAR_SCHEMA.field("close_time").nullable is False


def test_existing_quote_schema_is_unchanged_by_the_new_schemas() -> None:
    # Adding schemas must not change the physical layout of the published quote schema.
    assert QUOTE_SCHEMA.names == [
        "event_time",
        "available_at",
        "source_sequence",
        "instrument_id",
        "source_id",
        "schema_id",
        "bid",
        "ask",
        "bid_size",
        "ask_size",
        "source_flags",
    ]


def test_valid_trades_have_no_problems_and_null_size_is_not_zero() -> None:
    later = _trade(source_sequence=2, size=3.0, event_time=T1, available_at=T1)
    table = _table(TRADE_SCHEMA, [_trade(), later])
    assert validate_trades(table) == []
    assert table.column("size").to_pylist() == [None, 3.0]


def test_zero_or_negative_price_is_flagged_not_treated_as_missing() -> None:
    rows = [_trade(price=0.0), _trade(source_sequence=2, price=-1.0)]
    problems = validate_trades(_table(TRADE_SCHEMA, rows))
    assert sorted(p.row for p in problems if "price" in p.reason) == [0, 1]


def test_negative_size_is_flagged_and_null_size_is_not() -> None:
    rows = [_trade(size=-2.0), _trade(source_sequence=2, size=None)]
    problems = validate_trades(_table(TRADE_SCHEMA, rows))
    assert [p.row for p in problems] == [0]
    assert "size" in problems[0].reason


def test_trade_available_before_event_is_flagged() -> None:
    problems = validate_trades(_table(TRADE_SCHEMA, [_trade(available_at=T0, event_time=T1)]))
    assert [p.reason for p in problems] == ["available_at precedes event_time"]


def test_duplicate_trade_sequence_flags_every_occurrence() -> None:
    rows = [_trade(source_sequence=7), _trade(source_sequence=7, event_time=T1)]
    problems = validate_trades(_table(TRADE_SCHEMA, rows))
    assert sorted(p.row for p in problems if p.reason.startswith("duplicate")) == [0, 1]


def test_trade_quarantine_marks_only_failing_rows() -> None:
    rows = [_trade(), _trade(source_sequence=2, price=0.0), _trade(source_sequence=3)]
    table = _table(TRADE_SCHEMA, rows)
    mask = quarantine_mask(validate_trades(table), table.num_rows)
    assert mask.tolist() == [False, True, False]


def test_valid_sessions_have_no_problems() -> None:
    # Back-to-back intervals that touch at T1 do not overlap.
    rows = [
        _session(open_time=T0, close_time=T1),
        _session(session_name="late", open_time=T1, close_time=T2),
    ]
    assert validate_calendar(_table(CALENDAR_SCHEMA, rows)) == []


def test_session_that_does_not_close_after_it_opens_is_flagged() -> None:
    problems = validate_calendar(_table(CALENDAR_SCHEMA, [_session(open_time=T1, close_time=T0)]))
    assert [p.reason for p in problems] == ["close_time must follow open_time"]


def test_overlapping_sessions_of_one_instrument_are_flagged_on_the_later_one() -> None:
    rows = [
        _session(open_time=T0, close_time=T2),
        _session(session_name="late", open_time=T1, close_time=T2),
    ]
    problems = validate_calendar(_table(CALENDAR_SCHEMA, rows))
    assert [(p.row, p.reason) for p in problems] == [
        (1, "session overlaps a previous session of the same instrument")
    ]


def test_overlap_across_different_instruments_is_allowed() -> None:
    rows = [_session(), _session(instrument_id="US500")]
    assert validate_calendar(_table(CALENDAR_SCHEMA, rows)) == []


def test_trade_and_calendar_parquet_round_trip_preserves_schema_values_and_nulls(
    tmp_path: Path,
) -> None:
    trades = _table(TRADE_SCHEMA, [_trade(), _trade(source_sequence=2, size=3.0, event_time=T1)])
    calendar = _table(CALENDAR_SCHEMA, [_session()])
    trade_path = tmp_path / "trades.parquet"
    calendar_path = tmp_path / "calendar.parquet"
    pq.write_table(trades, trade_path)
    pq.write_table(calendar, calendar_path)
    back_trades = pq.read_table(trade_path)
    back_calendar = pq.read_table(calendar_path)
    assert back_trades.schema.equals(TRADE_SCHEMA)
    assert back_trades.column("size").to_pylist() == [None, 3.0]
    assert back_trades.column("event_time").to_pylist() == [T0, T1]
    assert back_calendar.schema.equals(CALENDAR_SCHEMA)
    assert back_calendar.column("close_time").to_pylist() == [T2]
