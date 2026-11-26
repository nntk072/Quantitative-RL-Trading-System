"""Physical Arrow/Parquet schemas and validators for normalized market events (DATA-SCHEMAS)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from market_data.arrow_schemas import (
    BAR_SCHEMA,
    CALENDAR_SCHEMA,
    CALENDAR_SCHEMA_ID,
    INSTRUMENT_SCHEMA,
    QUOTE_EVENT_SCHEMA_ID,
    QUOTE_SCHEMA,
    SCHEMA_VERSION,
    TRADE_SCHEMA,
    quarantine_mask,
    require_schema_id,
    validate_bars,
    validate_calendar,
    validate_quotes,
    validate_trades,
)

T0 = datetime(2026, 1, 2, 9, 30, tzinfo=UTC)
T1 = datetime(2026, 1, 2, 9, 31, tzinfo=UTC)


def _quote(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "event_time": T0,
        "available_at": T0,
        "source_sequence": 1,
        "instrument_id": "US100",
        "source_id": "mt5",
        "schema_id": QUOTE_EVENT_SCHEMA_ID,
        "origin": "observed",
        "bid": 100.0,
        "ask": 100.2,
        "bid_size": None,
        "ask_size": None,
        "source_flags": 0,
    }
    row.update(overrides)
    return row


def _bar(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "event_time": T0,
        "close_time": T1,
        "available_at": T1,
        "source_sequence": 1,
        "instrument_id": "US100",
        "source_id": "mt5",
        "schema_id": SCHEMA_VERSION,
        "open": 100.0,
        "high": 101.0,
        "low": 99.5,
        "close": 100.5,
        "volume": None,
    }
    row.update(overrides)
    return row


def _table(schema: pa.Schema, rows: list[dict[str, object]]) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=schema)


def test_time_fields_are_utc_nanoseconds_and_nullable_prices_are_declared() -> None:
    assert QUOTE_SCHEMA.field("event_time").type == pa.timestamp("ns", tz="UTC")
    assert QUOTE_SCHEMA.field("available_at").type == pa.timestamp("ns", tz="UTC")
    assert QUOTE_SCHEMA.field("bid").nullable is True
    assert BAR_SCHEMA.field("open").nullable is False
    assert INSTRUMENT_SCHEMA.field("valid_to").nullable is True


def test_valid_quotes_have_no_problems() -> None:
    table = _table(
        QUOTE_SCHEMA, [_quote(), _quote(source_sequence=2, event_time=T1, available_at=T1)]
    )
    assert validate_quotes(table) == []


def test_bid_above_ask_is_flagged() -> None:
    table = _table(QUOTE_SCHEMA, [_quote(bid=100.5, ask=100.2)])
    assert [p.reason for p in validate_quotes(table)] == ["bid exceeds ask"]


def test_missing_bid_is_null_not_a_zero_sentinel() -> None:
    table = _table(QUOTE_SCHEMA, [_quote(bid=None)])
    assert table.column("bid").null_count == 1
    assert validate_quotes(table) == []


def test_zero_price_is_flagged_as_invalid_not_as_missing() -> None:
    table = _table(QUOTE_SCHEMA, [_quote(bid=0.0)])
    assert [p.reason for p in validate_quotes(table)] == ["bid must be finite and positive"]


def test_availability_before_event_time_is_flagged() -> None:
    table = _table(QUOTE_SCHEMA, [_quote(event_time=T1, available_at=T0)])
    assert "available_at precedes event_time" in [p.reason for p in validate_quotes(table)]


def test_duplicate_instrument_sequence_flags_every_occurrence() -> None:
    table = _table(
        QUOTE_SCHEMA,
        [_quote(source_sequence=7), _quote(source_sequence=7, event_time=T1, available_at=T1)],
    )
    rows = [p.row for p in validate_quotes(table) if p.reason.startswith("duplicate")]
    assert rows == [0, 1]


def test_valid_bars_have_no_problems() -> None:
    assert validate_bars(_table(BAR_SCHEMA, [_bar()])) == []


def test_bar_bounds_violation_is_flagged() -> None:
    # high 100.0 is below close 100.5
    problems = validate_bars(_table(BAR_SCHEMA, [_bar(high=100.0)]))
    assert [p.reason for p in problems] == ["OHLC bounds violated"]


def test_incomplete_bar_is_flagged_by_availability() -> None:
    problems = validate_bars(_table(BAR_SCHEMA, [_bar(available_at=T0)]))
    assert "available_at precedes close_time (incomplete bar)" in [p.reason for p in problems]


def test_quarantine_mask_marks_only_failing_rows() -> None:
    table = _table(QUOTE_SCHEMA, [_quote(), _quote(source_sequence=2, bid=101.0, ask=100.0)])
    mask = quarantine_mask(validate_quotes(table), table.num_rows)
    assert mask.tolist() == [False, True]


def test_parquet_round_trip_preserves_schema_values_and_nulls(tmp_path: Path) -> None:
    table = _table(
        QUOTE_SCHEMA,
        [_quote(), _quote(source_sequence=2, bid=None, event_time=T1, available_at=T1)],
    )
    path = tmp_path / "quotes.parquet"
    pq.write_table(table, path)
    back = pq.read_table(path)
    assert back.schema.equals(QUOTE_SCHEMA)
    assert back.column("bid").to_pylist() == [100.0, None]
    assert back.column("event_time").to_pylist() == [T0, T1]


def test_duplicate_bar_open_time_is_flagged_on_every_occurrence() -> None:
    rows = [_bar(source_sequence=1), _bar(source_sequence=2)]
    problems = validate_bars(_table(BAR_SCHEMA, rows))
    assert sorted(p.row for p in problems if p.reason.startswith("duplicate bar")) == [0, 1]


def _trade(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "event_time": T0,
        "available_at": T0,
        "source_sequence": 1,
        "instrument_id": "US100",
        "source_id": "mt5",
        "schema_id": SCHEMA_VERSION,
        "price": 100.1,
        "size": None,
        "source_flags": 0,
    }
    row.update(overrides)
    return row


def _session(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "instrument_id": "US100",
        "session_open": T0,
        "session_close": T1,
        "session_kind": "trading",
        "source_id": "calendar",
        "schema_id": CALENDAR_SCHEMA_ID,
    }
    row.update(overrides)
    return row


def test_valid_trades_have_no_problems_and_null_size_is_allowed() -> None:
    table = _table(TRADE_SCHEMA, [_trade(), _trade(source_sequence=2, size=3.0)])
    assert validate_trades(table) == []
    assert table.column("size").null_count == 1


def test_trade_price_and_size_violations_are_flagged() -> None:
    table = _table(
        TRADE_SCHEMA,
        [
            _trade(price=0.0),
            _trade(source_sequence=2, size=-1.0),
            _trade(source_sequence=3, event_time=T1),
        ],
    )
    reasons = [(p.row, p.reason) for p in validate_trades(table)]
    assert (0, "price must be finite and positive") in reasons
    assert (1, "size must be finite and non-negative") in reasons
    assert (2, "available_at precedes event_time") in reasons


def test_duplicate_trade_sequence_flags_every_occurrence() -> None:
    table = _table(TRADE_SCHEMA, [_trade(source_sequence=5), _trade(source_sequence=5)])
    assert sorted(p.row for p in validate_trades(table) if p.reason.startswith("duplicate")) == [
        0,
        1,
    ]


def test_valid_calendar_sessions_have_no_problems() -> None:
    later = datetime(2026, 1, 2, 10, 0, tzinfo=UTC)
    table = _table(CALENDAR_SCHEMA, [_session(), _session(session_open=T1, session_close=later)])
    assert validate_calendar(table) == []


def test_calendar_reversed_and_unknown_kind_are_flagged() -> None:
    table = _table(
        CALENDAR_SCHEMA,
        [
            _session(session_open=T1, session_close=T0),
            _session(
                session_kind="halfday",
                session_open=T1,
                session_close=datetime(2026, 1, 2, 10, 0, tzinfo=UTC),
            ),
        ],
    )
    reasons = [(p.row, p.reason) for p in validate_calendar(table)]
    assert (0, "session_close must follow session_open") in reasons
    assert (1, "unknown session_kind 'halfday'") in reasons
    assert not any("overlaps" in reason for _, reason in reasons)


def test_calendar_overlapping_sessions_are_flagged_on_both_rows() -> None:
    overlap_end = datetime(2026, 1, 2, 9, 45, tzinfo=UTC)
    table = _table(
        CALENDAR_SCHEMA,
        [_session(), _session(session_open=T0, session_close=overlap_end)],
    )
    reasons = [(p.row, p.reason) for p in validate_calendar(table)]
    assert sorted(r for r, reason in reasons if "overlaps" in reason) == [0, 1]


def test_calendar_overlap_is_checked_per_instrument() -> None:
    table = _table(
        CALENDAR_SCHEMA,
        [_session(), _session(instrument_id="US500")],
    )
    assert validate_calendar(table) == []


def test_require_schema_id_accepts_the_supported_id_and_fails_closed() -> None:
    assert require_schema_id(_table(BAR_SCHEMA, [_bar()])) == SCHEMA_VERSION
    with pytest.raises(ValueError, match="unsupported schema_id"):
        require_schema_id(_table(BAR_SCHEMA, [_bar(schema_id="market-event.v0")]))
    with pytest.raises(ValueError, match="exactly one schema_id"):
        require_schema_id(
            _table(BAR_SCHEMA, [_bar(), _bar(schema_id="market-event.v0", source_sequence=2)])
        )
    with pytest.raises(ValueError, match="exactly one schema_id"):
        require_schema_id(_table(BAR_SCHEMA, []))
