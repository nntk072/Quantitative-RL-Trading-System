"""Null, order, schema-id, origin and instrument rules of the normalized market-data schemas (DATA-SCHEMAS)."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pytest

from market_data.arrow_schemas import (
    BAR_REVISED_SCHEMA_ID,
    BAR_SCHEMA,
    CALENDAR_SCHEMA,
    INSTRUMENT_SCHEMA,
    INSTRUMENT_SCHEMA_ID,
    LEGACY_QUOTE_SCHEMA,
    QUOTE_EVENT_SCHEMA_ID,
    QUOTE_SCHEMA,
    SCHEMA_VERSION,
    TRADE_SCHEMA,
    validate_bars,
    validate_calendar,
    validate_instruments,
    validate_quotes,
    validate_trades,
)
from market_data.event_schemas import normalized_events_from_arrays, validate_normalized_events

T0 = datetime(2025, 1, 2, 9, 30, tzinfo=UTC)
T1 = datetime(2025, 1, 2, 9, 31, tzinfo=UTC)
T2 = datetime(2025, 1, 2, 9, 32, tzinfo=UTC)
T3 = datetime(2025, 1, 2, 9, 33, tzinfo=UTC)


def _quote(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "event_time": T0,
        "available_at": T0,
        "source_sequence": 1,
        "instrument_id": "US100.cash",
        "source_id": "mt5-tick",
        "schema_id": QUOTE_EVENT_SCHEMA_ID,
        "origin": "observed",
        "bid": 100.0,
        "ask": 100.2,
        "bid_size": None,
        "ask_size": None,
        "source_flags": 6,
    }
    row.update(overrides)
    return row


def _bar(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "event_time": T0,
        "close_time": T1,
        "available_at": T1,
        "source_sequence": 1,
        "instrument_id": "US100.cash",
        "source_id": "mt5-export",
        "schema_id": SCHEMA_VERSION,
        "open": 100.0,
        "high": 101.0,
        "low": 99.5,
        "close": 100.5,
        "volume": 10.0,
    }
    row.update(overrides)
    return row


def _trade(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "event_time": T0,
        "available_at": T0,
        "source_sequence": 1,
        "instrument_id": "US100.cash",
        "source_id": "mt5-tick",
        "schema_id": SCHEMA_VERSION,
        "price": 100.1,
        "size": 2.0,
        "source_flags": 0,
    }
    row.update(overrides)
    return row


def _instrument(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "instrument_id": "US100.cash",
        "contract_size": 1.0,
        "price_tick": 0.01,
        "lot_step": 0.1,
        "currency": "USD",
        "session_calendar": "config/ny_session_schedule.csv",
        "valid_from": T0,
        "valid_to": None,
        "source_id": "registry",
        "schema_id": INSTRUMENT_SCHEMA_ID,
    }
    row.update(overrides)
    return row


def _table(schema: pa.Schema, rows: list[dict[str, object]]) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=schema)


def _reasons(problems: list) -> list[tuple[int, str]]:  # type: ignore[type-arg]
    return [(p.row, p.reason) for p in problems]


def test_null_event_time_is_a_row_defect_not_a_1970_timestamp() -> None:
    table = _table(QUOTE_SCHEMA, [_quote(), _quote(source_sequence=2, event_time=None)])
    assert _reasons(validate_quotes(table)) == [(1, "null in non-nullable field event_time")]


def test_null_bar_open_is_reported_as_a_null_not_as_a_price_rule() -> None:
    assert _reasons(validate_bars(_table(BAR_SCHEMA, [_bar(open=None)]))) == [
        (0, "null in non-nullable field open")
    ]


def test_null_trade_price_is_reported_as_a_null() -> None:
    assert _reasons(validate_trades(_table(TRADE_SCHEMA, [_trade(price=None)]))) == [
        (0, "null in non-nullable field price")
    ]


def test_quote_event_times_that_move_backwards_in_sequence_are_flagged() -> None:
    rows = [_quote(event_time=T1, available_at=T1), _quote(source_sequence=2, event_time=T0)]
    assert _reasons(validate_quotes(_table(QUOTE_SCHEMA, rows))) == [
        (1, "event_time precedes the previous row in source_sequence order")
    ]


def test_equal_event_times_ordered_by_sequence_are_not_an_order_defect() -> None:
    rows = [_quote(), _quote(source_sequence=2)]
    assert validate_quotes(_table(QUOTE_SCHEMA, rows)) == []


def test_order_is_checked_per_instrument() -> None:
    rows = [
        _quote(event_time=T1, available_at=T1),
        _quote(source_sequence=2, instrument_id="US500.cash", event_time=T0, available_at=T0),
    ]
    assert validate_quotes(_table(QUOTE_SCHEMA, rows)) == []


def test_bar_event_times_that_move_backwards_are_flagged() -> None:
    rows = [_bar(event_time=T1, close_time=T2, available_at=T2), _bar(source_sequence=2)]
    reasons = _reasons(validate_bars(_table(BAR_SCHEMA, rows)))
    assert (1, "event_time precedes the previous row in source_sequence order") in reasons


def test_trade_event_times_that_move_backwards_are_flagged() -> None:
    rows = [_trade(event_time=T1, available_at=T1), _trade(source_sequence=2, event_time=T0)]
    assert _reasons(validate_trades(_table(TRADE_SCHEMA, rows))) == [
        (1, "event_time precedes the previous row in source_sequence order")
    ]


def test_negative_and_nan_quote_sizes_are_flagged() -> None:
    rows = [
        _quote(bid_size=-5.0),
        _quote(source_sequence=2, ask_size=float("nan")),
    ]
    assert _reasons(validate_quotes(_table(QUOTE_SCHEMA, rows))) == [
        (0, "bid_size must be finite and non-negative"),
        (1, "ask_size must be finite and non-negative"),
    ]


def test_negative_and_nan_bar_volume_are_flagged_and_null_volume_is_allowed() -> None:
    rows = [
        _bar(volume=-3.0),
        _bar(source_sequence=2, event_time=T1, close_time=T2, available_at=T2, volume=float("nan")),
        _bar(source_sequence=3, event_time=T2, close_time=T3, available_at=T3, volume=None),
    ]
    assert _reasons(validate_bars(_table(BAR_SCHEMA, rows))) == [
        (0, "volume must be finite and non-negative"),
        (1, "volume must be finite and non-negative"),
    ]


def test_a_quote_with_no_origin_tag_is_refused_as_a_null() -> None:
    table = pa.Table.from_pylist([_quote(origin=None)], schema=QUOTE_SCHEMA)
    assert _reasons(validate_quotes(table)) == [(0, "null in non-nullable field origin")]


def test_a_quote_with_an_unknown_origin_is_flagged() -> None:
    assert _reasons(validate_quotes(_table(QUOTE_SCHEMA, [_quote(origin="guessed")]))) == [
        (0, "origin must be 'observed' or 'ohlc_synthetic' (untagged quote)")
    ]


def test_an_ohlc_derived_quote_is_accepted_only_with_its_explicit_tag() -> None:
    rows = [_quote(origin="ohlc_synthetic"), _quote(source_sequence=2, origin="observed")]
    assert validate_quotes(_table(QUOTE_SCHEMA, rows)) == []


def test_a_legacy_untagged_quote_table_is_refused_by_the_current_validator() -> None:
    legacy_row = {k: v for k, v in _quote().items() if k != "origin"}
    legacy_row["schema_id"] = SCHEMA_VERSION
    legacy = pa.Table.from_pylist([legacy_row], schema=LEGACY_QUOTE_SCHEMA)
    with pytest.raises(ValueError, match="unsupported schema_id 'market-event.v1'"):
        validate_quotes(legacy)


def test_a_bar_schema_id_is_refused_on_a_quote_table() -> None:
    with pytest.raises(ValueError, match="unsupported schema_id"):
        validate_quotes(_table(QUOTE_SCHEMA, [_quote(schema_id=BAR_REVISED_SCHEMA_ID)]))


def test_quote_table_missing_a_required_column_is_refused() -> None:
    table = pa.Table.from_pylist([_quote()], schema=QUOTE_SCHEMA).drop_columns(["origin"])
    with pytest.raises(ValueError, match="missing columns"):
        validate_quotes(table)


def test_normalized_quote_with_bid_above_ask_is_flagged() -> None:
    table = normalized_events_from_arrays(
        event_time=np.array([np.datetime64("2025-01-02T09:30:00", "ns")]),
        available_at=np.array([np.datetime64("2025-01-02T09:30:00", "ns")]),
        source_sequence=np.array([1]),
        instrument_id="US100.cash",
        source_id="mt5",
        event_type="quote",
        values={"value_a": np.array([101.0]), "value_b": np.array([100.0])},
    )
    assert _reasons(validate_normalized_events(table)) == [(0, "bid exceeds ask")]


def test_normalized_events_refuse_a_foreign_schema_id() -> None:
    table = normalized_events_from_arrays(
        event_time=np.array([np.datetime64("2025-01-02T09:30:00", "ns")]),
        available_at=np.array([np.datetime64("2025-01-02T09:30:00", "ns")]),
        source_sequence=np.array([1]),
        instrument_id="US100.cash",
        source_id="mt5",
        event_type="trade",
        values={"value_a": np.array([100.0])},
    )
    foreign = table.set_column(
        table.schema.get_field_index("schema_id"),
        "schema_id",
        pa.array([QUOTE_EVENT_SCHEMA_ID], type=pa.string()),
    )
    with pytest.raises(ValueError, match="unsupported schema_id"):
        validate_normalized_events(foreign)


def test_calendar_refuses_a_bar_schema_id() -> None:
    row = {
        "instrument_id": "US100.cash",
        "session_open": T0,
        "session_close": T1,
        "session_kind": "trading",
        "source_id": "calendar",
        "schema_id": SCHEMA_VERSION,
    }
    with pytest.raises(ValueError, match="unsupported schema_id"):
        validate_calendar(pa.Table.from_pylist([row], schema=CALENDAR_SCHEMA))


def test_a_valid_instrument_has_no_problems() -> None:
    assert validate_instruments(_table(INSTRUMENT_SCHEMA, [_instrument()])) == []


def test_instrument_tick_lot_and_contract_must_be_finite_and_positive() -> None:
    rows = [
        _instrument(price_tick=0.0),
        _instrument(instrument_id="US500.cash", lot_step=float("nan")),
        _instrument(instrument_id="GER40.cash", contract_size=-1.0),
    ]
    assert _reasons(validate_instruments(_table(INSTRUMENT_SCHEMA, rows))) == [
        (0, "price_tick must be finite and positive"),
        (1, "lot_step must be finite and positive"),
        (2, "contract_size must be finite and positive"),
    ]


def test_instrument_currency_and_session_calendar_are_checked() -> None:
    rows = [
        _instrument(currency="usd"),
        _instrument(instrument_id="US500.cash", session_calendar=" "),
    ]
    assert _reasons(validate_instruments(_table(INSTRUMENT_SCHEMA, rows))) == [
        (0, "currency must be a three-letter upper-case code"),
        (1, "session_calendar is required"),
    ]


def test_overlapping_validity_intervals_for_one_instrument_are_flagged_on_both_rows() -> None:
    rows = [
        _instrument(valid_from=T0, valid_to=T2),
        _instrument(valid_from=T1, valid_to=None),
    ]
    assert _reasons(validate_instruments(_table(INSTRUMENT_SCHEMA, rows))) == [
        (0, "validity interval overlaps the next interval"),
        (1, "validity interval overlaps the previous interval"),
    ]


def test_adjacent_validity_intervals_and_other_instruments_do_not_overlap() -> None:
    rows = [
        _instrument(valid_from=T0, valid_to=T1),
        _instrument(valid_from=T1, valid_to=None),
        _instrument(instrument_id="US500.cash", valid_from=T0, valid_to=None),
    ]
    assert validate_instruments(_table(INSTRUMENT_SCHEMA, rows)) == []


def test_instrument_validity_must_end_after_it_starts() -> None:
    assert _reasons(
        validate_instruments(_table(INSTRUMENT_SCHEMA, [_instrument(valid_to=T0)]))
    ) == [(0, "valid_to must follow valid_from")]


def test_instrument_refuses_a_quote_schema_id() -> None:
    with pytest.raises(ValueError, match="unsupported schema_id"):
        validate_instruments(
            _table(INSTRUMENT_SCHEMA, [_instrument(schema_id=QUOTE_EVENT_SCHEMA_ID)])
        )
