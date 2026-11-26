"""Second schema id, fail-closed acceptance, explicit v1-to-v2 migration and the append-only correction policy."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from market_data.arrow_schemas import (
    BAR_REVISED_SCHEMA,
    BAR_REVISED_SCHEMA_ID,
    BAR_SCHEMA,
    LEGACY_QUOTE_SCHEMA,
    QUOTE_EVENT_SCHEMA_ID,
    QUOTE_SCHEMA,
    SCHEMA_VERSION,
    require_schema_id,
    validate_quotes,
)
from market_data.schema_migration import (
    append_correction,
    latest_revision,
    migrate_bars_v1_to_v2,
    migrate_quotes_v1_to_quote_v1,
    validate_revised_bars,
)

T0 = datetime(2026, 1, 2, 9, 30, tzinfo=UTC)
T1 = datetime(2026, 1, 2, 9, 31, tzinfo=UTC)


def _v1_bar(event: datetime, close: float = 100.5, sequence: int = 1) -> dict[str, object]:
    return {
        "event_time": event,
        "close_time": datetime(
            event.year, event.month, event.day, event.hour, event.minute + 1, tzinfo=UTC
        ),
        "available_at": datetime(
            event.year, event.month, event.day, event.hour, event.minute + 1, tzinfo=UTC
        ),
        "source_sequence": sequence,
        "instrument_id": "US100",
        "source_id": "mt5",
        "schema_id": SCHEMA_VERSION,
        "open": 100.0,
        "high": 101.0,
        "low": 99.5,
        "close": close,
        "volume": None,
    }


def _v1_table(rows: list[dict[str, object]]) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=BAR_SCHEMA)


def _v2_row(event: datetime, revision: int, close: float = 100.5) -> dict[str, object]:
    row = _v1_bar(event, close=close, sequence=1)
    row["schema_id"] = BAR_REVISED_SCHEMA_ID
    row["revision"] = revision
    return row


def _v2_table(rows: list[dict[str, object]]) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=BAR_REVISED_SCHEMA)


def test_migration_writes_the_second_schema_id_with_revision_zero_and_keeps_every_value() -> None:
    v1 = _v1_table([_v1_bar(T0), _v1_bar(T1, close=100.75, sequence=2)])
    v2 = migrate_bars_v1_to_v2(v1)
    assert v2.schema.equals(BAR_REVISED_SCHEMA)
    assert set(v2.column("schema_id").to_pylist()) == {BAR_REVISED_SCHEMA_ID}
    assert v2.column("revision").to_pylist() == [0, 0]
    assert v2.column("close").to_pylist() == [100.5, 100.75]
    assert v2.column("event_time").to_pylist() == v1.column("event_time").to_pylist()
    assert validate_revised_bars(v2) == []


def test_migration_refuses_a_table_that_is_already_v2() -> None:
    with pytest.raises(ValueError, match="unsupported schema_id"):
        migrate_bars_v1_to_v2(_v2_table([_v2_row(T0, 0)]))


def test_migration_refuses_an_unknown_id_and_an_invalid_v1_bar() -> None:
    unknown = _v1_table([_v1_bar(T0)])
    unknown = unknown.set_column(
        unknown.schema.get_field_index("schema_id"),
        "schema_id",
        pa.array(["market-event.v9"], type=pa.string()),
    )
    with pytest.raises(ValueError, match="unsupported schema_id"):
        migrate_bars_v1_to_v2(unknown)
    invalid = _v1_table([_v1_bar(T0, close=102.0)])  # close above high
    with pytest.raises(ValueError, match="cannot migrate invalid v1 bars"):
        migrate_bars_v1_to_v2(invalid)


def test_a_v1_reader_fails_closed_on_the_second_schema_id() -> None:
    v2 = _v2_table([_v2_row(T0, 0)])
    assert require_schema_id(v2) == BAR_REVISED_SCHEMA_ID
    with pytest.raises(ValueError, match="unsupported schema_id"):
        require_schema_id(v2, accepted=frozenset({SCHEMA_VERSION}))


def test_a_mixed_v1_and_v2_table_is_refused_as_mixed() -> None:
    mixed = pa.Table.from_pylist([_v1_bar(T0), _v2_row(T1, 0)], schema=BAR_REVISED_SCHEMA)
    with pytest.raises(ValueError, match="exactly one schema_id"):
        require_schema_id(mixed)


def test_correction_is_appended_as_the_next_revision_and_the_original_row_stays() -> None:
    history = _v2_table([_v2_row(T0, 0, close=100.5)])
    correction = _v2_table([_v2_row(T0, 0, close=100.25)])
    merged = append_correction(history, correction)
    assert merged.num_rows == 2
    assert merged.column("revision").to_pylist() == [0, 1]
    assert merged.column("close").to_pylist() == [100.5, 100.25]
    current = latest_revision(merged)
    assert current.num_rows == 1
    assert current.column("revision").to_pylist() == [1]
    assert current.column("close").to_pylist() == [100.25]


def test_a_second_correction_takes_revision_two_and_a_new_bar_starts_at_zero() -> None:
    history = _v2_table([_v2_row(T0, 0, close=100.5)])
    once = append_correction(history, _v2_table([_v2_row(T0, 0, close=100.25)]))
    twice = append_correction(
        once, _v2_table([_v2_row(T0, 0, close=100.0), _v2_row(T1, 0, close=100.5)])
    )
    revisions = [(r["event_time"], r["revision"]) for r in twice.to_pylist()]
    assert revisions == [(T0, 0), (T0, 1), (T0, 2), (T1, 0)]
    assert latest_revision(twice).column("revision").to_pylist() == [2, 0]


def test_a_correction_in_the_wrong_schema_is_refused() -> None:
    history = _v2_table([_v2_row(T0, 0)])
    with pytest.raises(ValueError, match="unsupported schema_id"):
        append_correction(history, _v1_table([_v1_bar(T0)]))


def test_duplicate_revision_and_negative_revision_are_flagged() -> None:
    table = _v2_table([_v2_row(T0, 0), _v2_row(T0, 0, close=100.25), _v2_row(T1, -1)])
    reasons = [(p.row, p.reason) for p in validate_revised_bars(table)]
    assert (0, "duplicate (instrument, event_time, revision)") in reasons
    assert (1, "duplicate (instrument, event_time, revision)") in reasons
    assert (2, "revision must be non-negative") in reasons


def test_bar_rules_still_apply_to_each_revision() -> None:
    bad = _v2_table([_v2_row(T0, 0, close=102.0)])
    assert [p.reason for p in validate_revised_bars(bad)] == ["OHLC bounds violated"]


def test_a_revised_table_round_trips_through_parquet_with_its_schema_id(tmp_path: Path) -> None:
    table = append_correction(
        _v2_table([_v2_row(T0, 0)]), _v2_table([_v2_row(T0, 0, close=100.25)])
    )
    path = tmp_path / "bars_v2.parquet"
    pq.write_table(table, path)
    back = pq.read_table(path)
    assert back.schema.equals(BAR_REVISED_SCHEMA)
    assert back.column("revision").to_pylist() == [0, 1]
    assert set(back.column("schema_id").to_pylist()) == {BAR_REVISED_SCHEMA_ID}
    assert validate_revised_bars(back) == []


def _legacy_quote_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "event_time": datetime(2025, 1, 2, 9, 30, tzinfo=UTC),
        "available_at": datetime(2025, 1, 2, 9, 30, tzinfo=UTC),
        "source_sequence": 1,
        "instrument_id": "US100.cash",
        "source_id": "mt5-tick",
        "schema_id": SCHEMA_VERSION,
        "bid": 100.0,
        "ask": 100.2,
        "bid_size": None,
        "ask_size": None,
        "source_flags": 6,
    }
    row.update(overrides)
    return row


def test_quote_migration_tags_every_legacy_row_observed_under_the_second_schema_id(
    tmp_path: Path,
) -> None:
    legacy = pa.Table.from_pylist(
        [
            _legacy_quote_row(),
            _legacy_quote_row(
                source_sequence=2,
                event_time=datetime(2025, 1, 2, 9, 31, tzinfo=UTC),
                available_at=datetime(2025, 1, 2, 9, 31, tzinfo=UTC),
                bid=None,
            ),
        ],
        schema=LEGACY_QUOTE_SCHEMA,
    )
    migrated = migrate_quotes_v1_to_quote_v1(legacy)
    assert migrated.schema.equals(QUOTE_SCHEMA)
    assert migrated.column("origin").to_pylist() == ["observed", "observed"]
    assert set(migrated.column("schema_id").to_pylist()) == {QUOTE_EVENT_SCHEMA_ID}
    assert migrated.column("bid").to_pylist() == [100.0, None]
    assert validate_quotes(migrated) == []
    path = tmp_path / "quotes.parquet"
    pq.write_table(migrated, path)
    assert pq.read_table(path).equals(migrated)


def test_quote_migration_refuses_a_table_already_in_the_quote_layout() -> None:
    current = pa.Table.from_pylist(
        [_legacy_quote_row(schema_id=QUOTE_EVENT_SCHEMA_ID, origin="observed")],
        schema=QUOTE_SCHEMA,
    )
    with pytest.raises(ValueError, match="not a legacy quote table"):
        migrate_quotes_v1_to_quote_v1(current)


def test_quote_migration_refuses_a_bar_table_passed_as_quotes() -> None:
    bars = _v1_table([_v1_bar(datetime(2025, 1, 2, 9, 30, tzinfo=UTC))])
    with pytest.raises(ValueError, match="not a legacy quote table"):
        migrate_quotes_v1_to_quote_v1(bars)


def test_quote_migration_refuses_an_invalid_legacy_quote() -> None:
    crossed = pa.Table.from_pylist(
        [_legacy_quote_row(bid=100.5, ask=100.2)], schema=LEGACY_QUOTE_SCHEMA
    )
    with pytest.raises(ValueError, match="cannot migrate invalid legacy quotes: bid exceeds ask"):
        migrate_quotes_v1_to_quote_v1(crossed)


def test_quote_migration_of_an_empty_legacy_table_is_an_empty_quote_table() -> None:
    empty = pa.Table.from_pylist([], schema=LEGACY_QUOTE_SCHEMA)
    migrated = migrate_quotes_v1_to_quote_v1(empty)
    assert migrated.num_rows == 0
    assert migrated.schema.equals(QUOTE_SCHEMA)


def test_a_revision_with_a_null_is_a_row_defect_not_a_type_error() -> None:
    rows = [_v2_row(datetime(2025, 1, 2, 9, 30, tzinfo=UTC), 0)]
    rows[0]["revision"] = None
    problems = validate_revised_bars(pa.Table.from_pylist(rows, schema=BAR_REVISED_SCHEMA))
    assert [(p.row, p.reason) for p in problems] == [(0, "null in non-nullable field revision")]
