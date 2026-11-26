"""Normalized event and feature-row schemas: validators, nulls, causality and Parquet round trip (DATA-SCHEMAS)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from market_data.arrow_schemas import (
    FEATURE_ROW_SCHEMA_ID,
    NORMALIZED_EVENT_SCHEMA_ID,
    require_schema_id,
)
from market_data.event_schemas import (
    FEATURE_ROW_SCHEMA,
    NORMALIZED_EVENT_SCHEMA,
    normalized_events_from_arrays,
    validate_feature_rows,
    validate_normalized_events,
)

T0 = datetime(2026, 1, 2, 9, 30, tzinfo=UTC)
T1 = datetime(2026, 1, 2, 9, 31, tzinfo=UTC)
T0_NS = np.datetime64("2026-01-02T09:30:00", "ns")
T1_NS = np.datetime64("2026-01-02T09:31:00", "ns")


def _events(kind: str, **values: np.ndarray) -> pa.Table:  # type: ignore[type-arg]
    return normalized_events_from_arrays(
        event_time=np.array([T0_NS, T1_NS]),
        available_at=np.array([T0_NS, T1_NS]),
        source_sequence=np.array([1, 2]),
        instrument_id="US100.cash",
        source_id="mt5",
        event_type=kind,
        values=dict(values),
    )


def _quote_table() -> pa.Table:
    return _events("quote", value_a=np.array([100.0, 100.1]), value_b=np.array([100.2, 100.3]))


def _bar_table() -> pa.Table:
    return _events(
        "bar",
        value_a=np.array([100.0, 100.0]),
        value_b=np.array([101.0, 101.0]),
        value_c=np.array([99.0, 99.0]),
        value_d=np.array([100.5, 100.5]),
        size=np.array([10.0, 12.0]),
    )


def test_builders_produce_the_declared_schema_and_null_non_applicable_fields() -> None:
    quotes = _quote_table()
    assert quotes.schema.equals(NORMALIZED_EVENT_SCHEMA)
    assert quotes.column("value_c").null_count == 2
    assert quotes.column("size").null_count == 2
    assert set(quotes.column("schema_id").to_pylist()) == {NORMALIZED_EVENT_SCHEMA_ID}
    assert require_schema_id(quotes) == NORMALIZED_EVENT_SCHEMA_ID


def test_valid_quotes_trades_and_bars_have_no_problems() -> None:
    assert validate_normalized_events(_quote_table()) == []
    assert validate_normalized_events(_bar_table()) == []
    trades = normalized_events_from_arrays(
        event_time=np.array([T0_NS]),
        available_at=np.array([T0_NS]),
        source_sequence=np.array([1]),
        instrument_id="US100.cash",
        source_id="mt5",
        event_type="trade",
        values={"value_a": np.array([100.1]), "size": np.array([3.0])},
    )
    assert validate_normalized_events(trades) == []


def test_unknown_event_type_is_flagged_and_not_checked_further() -> None:
    table = _events("quote", value_a=np.array([100.0, 100.1]), value_b=np.array([100.2, 100.3]))
    bad = table.set_column(
        table.schema.get_field_index("event_type"), "event_type", pa.array(["tick", "quote"])
    )
    assert [(p.row, p.reason) for p in validate_normalized_events(bad)] == [
        (0, "unknown event_type 'tick'")
    ]


def test_a_quote_missing_its_ask_is_flagged_not_filled_with_zero() -> None:
    table = _events("quote", value_a=np.array([100.0, 100.1]), value_b=np.array([100.2, 100.3]))
    index = table.schema.get_field_index("value_b")
    one_sided = table.set_column(index, "value_b", pa.array([None, 100.3], type=pa.float64()))
    assert [(p.row, p.reason) for p in validate_normalized_events(one_sided)] == [
        (0, "quote requires value_b")
    ]


def test_a_trade_carrying_bar_fields_is_flagged() -> None:
    table = normalized_events_from_arrays(
        event_time=np.array([T0_NS]),
        available_at=np.array([T0_NS]),
        source_sequence=np.array([1]),
        instrument_id="US100.cash",
        source_id="mt5",
        event_type="trade",
        values={"value_a": np.array([100.1]), "value_b": np.array([100.4])},
    )
    assert "trade must leave value_b null" in [p.reason for p in validate_normalized_events(table)]


def test_bar_ohlc_bounds_and_zero_prices_are_flagged() -> None:
    table = _events(
        "bar",
        value_a=np.array([100.0, 0.0]),
        value_b=np.array([100.0, 101.0]),
        value_c=np.array([99.0, 99.0]),
        value_d=np.array([100.5, 100.5]),
    )
    reasons = [(p.row, p.reason) for p in validate_normalized_events(table)]
    assert (0, "OHLC bounds violated") in reasons
    assert (1, "value_a must be finite and positive") in reasons


def test_availability_before_event_time_and_duplicate_sequence_are_flagged() -> None:
    table = normalized_events_from_arrays(
        event_time=np.array([T1_NS, T0_NS]),
        available_at=np.array([T0_NS, T0_NS]),
        source_sequence=np.array([7, 7]),
        instrument_id="US100.cash",
        source_id="mt5",
        event_type="quote",
        values={"value_a": np.array([100.0, 100.0]), "value_b": np.array([100.2, 100.2])},
    )
    reasons = validate_normalized_events(table)
    assert [p.reason for p in reasons if p.row == 0] == [
        "available_at precedes event_time",
        "duplicate (instrument, source_sequence)",
    ]
    assert sorted(p.row for p in reasons if p.reason.startswith("duplicate")) == [0, 1]


def _feature_table(
    values: list[list[float | None]], available: Sequence[Any] | None = None
) -> pa.Table:
    rows = len(values)
    times = [T0_NS + np.timedelta64(i, "m") for i in range(rows)]
    avail = available if available is not None else times
    return pa.table(
        {
            "event_time": pa.array(
                np.array(times, dtype="datetime64[ns]"), type=pa.timestamp("ns", tz="UTC")
            ),
            "available_at": pa.array(
                np.array(avail, dtype="datetime64[ns]"), type=pa.timestamp("ns", tz="UTC")
            ),
            "instrument_id": pa.array(["US100.cash"] * rows, type=pa.string()),
            "feature_set_id": pa.array(["m1-core"] * rows, type=pa.string()),
            "feature_version": pa.array(["v1"] * rows, type=pa.string()),
            "content_hash": pa.array(["abc123"] * rows, type=pa.string()),
            "schema_id": pa.array([FEATURE_ROW_SCHEMA_ID] * rows, type=pa.string()),
            "session_eligible": pa.array([True] * rows, type=pa.bool_()),
            "values": pa.array(
                values, type=pa.list_(pa.field("item", pa.float64(), nullable=True))
            ),
        },
        schema=FEATURE_ROW_SCHEMA,
    )


def test_valid_feature_rows_allow_explicit_nulls_for_warm_up() -> None:
    table = _feature_table([[None, 1.5], [2.0, 2.5]])
    assert validate_feature_rows(table, ["ema_20", "atr_14"]) == []
    assert table.column("values").to_pylist() == [[None, 1.5], [2.0, 2.5]]


def test_feature_width_mismatch_is_a_schema_error_not_a_row_defect() -> None:
    table = _feature_table([[1.0, 2.0]])
    with pytest.raises(ValueError, match="expected 3"):
        validate_feature_rows(table, ["a", "b", "c"])


def test_nan_feature_value_is_refused_in_favour_of_null() -> None:
    table = _feature_table([[float("nan"), 1.0]])
    assert [p.reason for p in validate_feature_rows(table, ["a", "b"])] == [
        "feature value must be finite or null, not NaN or inf"
    ]


def test_feature_using_information_after_its_event_time_is_flagged() -> None:
    later = [T1_NS, T1_NS]
    table = _feature_table([[1.0], [2.0]], available=later)
    reasons = validate_feature_rows(table, ["a"])
    assert [p.row for p in reasons if "after its event_time" in p.reason] == [0]


def test_duplicate_decision_clock_row_is_flagged_on_every_occurrence() -> None:
    table = _feature_table([[1.0], [2.0]])
    times = pa.array(
        np.array([T0_NS, T0_NS], dtype="datetime64[ns]"), type=pa.timestamp("ns", tz="UTC")
    )
    table = table.set_column(table.schema.get_field_index("event_time"), "event_time", times)
    assert sorted(
        p.row for p in validate_feature_rows(table, ["a"]) if "duplicate" in p.reason
    ) == [0, 1]


def test_mixed_feature_sets_are_refused() -> None:
    table = _feature_table([[1.0], [2.0]])
    mixed = table.set_column(
        table.schema.get_field_index("feature_set_id"),
        "feature_set_id",
        pa.array(["m1-core", "m5-core"], type=pa.string()),
    )
    with pytest.raises(ValueError, match="one feature_set_id"):
        validate_feature_rows(mixed, ["a"])


def test_normalized_and_feature_tables_round_trip_through_parquet_and_polars(
    tmp_path: Path,
) -> None:
    pl = pytest.importorskip("polars")
    events = _bar_table()
    features = _feature_table([[None, 1.5], [2.0, 2.5]])
    for name, table in (("events", events), ("features", features)):
        path = tmp_path / f"{name}.parquet"
        pq.write_table(table, path)
        back_arrow = pq.read_table(path)
        assert back_arrow.schema.equals(table.schema)
        assert back_arrow.equals(table)
        frame = pl.read_parquet(path)
        assert frame.height == table.num_rows
    polars_values = pl.read_parquet(tmp_path / "features.parquet")["values"].to_list()
    assert polars_values == [[None, 1.5], [2.0, 2.5]]
    assert pl.read_parquet(tmp_path / "events.parquet")["value_d"].to_list() == [100.5, 100.5]


def test_feature_row_with_no_content_hash_is_a_row_defect() -> None:
    table = _feature_table([[1.0], [2.0]])
    hashes = pa.array([None, "abc123"], type=pa.string())
    table = table.set_column(table.schema.get_field_index("content_hash"), "content_hash", hashes)
    assert [(p.row, p.reason) for p in validate_feature_rows(table, ["a"])] == [
        (0, "null in non-nullable field content_hash")
    ]


def test_a_null_feature_row_is_a_row_defect_not_a_width_error() -> None:
    table = _feature_table([[1.0], [2.0]])
    values = pa.array([None, [2.0]], type=pa.list_(pa.field("item", pa.float64(), nullable=True)))
    table = table.set_column(table.schema.get_field_index("values"), "values", values)
    assert [(p.row, p.reason) for p in validate_feature_rows(table, ["a"])] == [
        (0, "null in non-nullable field values")
    ]
