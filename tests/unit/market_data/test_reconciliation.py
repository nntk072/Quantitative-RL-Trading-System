"""Row-wise reconciliation, independent DST oracle, quarantine record and Parquet round trip (DATA-SCHEMAS)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]

from market_data.arrow_schemas import BAR_SCHEMA, RowProblem, mt5_export_to_bars
from market_data.reconciliation import (
    QUARANTINE_SCHEMA,
    independent_utc_open,
    parquet_round_trip,
    quarantine_table,
    reconcile_export_to_bars,
)


def _frame(rows: list[tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "DATE": [d for d, _ in rows],
            "TIME": [t for _, t in rows],
            "OPEN": ["100.0"] * len(rows),
            "HIGH": ["101.0"] * len(rows),
            "LOW": ["99.0"] * len(rows),
            "CLOSE": ["100.5"] * len(rows),
            "TICKVOL": ["10"] * len(rows),
        }
    )


def _convert(frame: pd.DataFrame) -> tuple[pa.Table, list[RowProblem]]:
    return mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")


def test_independent_oracle_classifies_normal_spring_forward_and_fall_back_labels() -> None:
    winter = independent_utc_open("2025.01.02", "09:30:00")
    assert winter.dst_class == "ok"
    assert winter.utc == datetime(2025, 1, 2, 7, 30, tzinfo=UTC)

    gap = independent_utc_open("2025.03.30", "03:30:00")
    assert (gap.utc, gap.dst_class) == (None, "nonexistent")

    repeated = independent_utc_open("2025.10.26", "03:30:00")
    assert (repeated.utc, repeated.dst_class) == (None, "ambiguous")

    after_gap = independent_utc_open("2025.03.30", "04:30:00")
    assert after_gap.utc == datetime(2025, 3, 30, 1, 30, tzinfo=UTC)


def test_reconciliation_accounts_for_dst_rows_and_matches_the_oracle() -> None:
    frame = _frame(
        [
            ("2025.03.30", "03:30:00"),  # nonexistent
            ("2025.03.30", "04:30:00"),
            ("2025.10.26", "03:30:00"),  # ambiguous
            ("2025.10.26", "04:30:00"),
        ]
    )
    table, problems = _convert(frame)
    result = reconcile_export_to_bars(frame, table, problems)
    assert result.reconciles
    assert (result.source_rows, result.converted_rows, result.quarantined_rows) == (4, 2, 2)
    assert result.unexplained_rows == 0


def test_a_corrupted_price_is_a_value_mismatch() -> None:
    frame = _frame([("2025.01.02", "09:30:00"), ("2025.01.02", "09:31:00")])
    table, problems = _convert(frame)
    index = table.schema.get_field_index("close")
    corrupted = table.set_column(index, "close", pa.array([100.5, 100.75], type=pa.float64()))
    result = reconcile_export_to_bars(frame, corrupted, problems)
    assert result.value_mismatches == 1
    assert not result.reconciles


def test_a_shifted_event_time_is_an_oracle_mismatch() -> None:
    frame = _frame([("2025.01.02", "09:30:00")])
    table, problems = _convert(frame)
    index = table.schema.get_field_index("event_time")
    shifted = pa.array(
        [datetime(2025, 1, 2, 7, 31, tzinfo=UTC)], type=BAR_SCHEMA.field("event_time").type
    )
    result = reconcile_export_to_bars(
        frame, table.set_column(index, "event_time", shifted), problems
    )
    assert result.event_time_mismatches == 1
    assert not result.reconciles


def test_a_silently_dropped_source_row_is_unexplained() -> None:
    frame = _frame([("2025.01.02", "09:30:00"), ("2025.01.02", "09:31:00")])
    table, problems = _convert(frame)
    result = reconcile_export_to_bars(frame, table.slice(0, 1), problems)
    assert result.unexplained_rows == 1
    assert not result.reconciles


def test_quarantine_record_names_each_problem_and_its_action() -> None:
    frame = _frame([("2025.03.30", "03:30:00"), ("2025.01.02", "09:31:00")])
    frame.loc[1, "HIGH"] = "100.0"  # high below close: OHLC rule
    table, problems = _convert(frame)
    kept = set(table.column("source_sequence").to_pylist())
    record = quarantine_table(frame, problems, kept)
    assert record.schema.equals(QUARANTINE_SCHEMA)
    rows = record.to_pylist()
    assert [(r["source_row_index"], r["action"]) for r in rows] == [
        (0, "excluded_from_table"),
        (1, "excluded_from_table"),
    ]
    assert rows[0]["reason"] == "nonexistent local time (DST spring-forward)"
    assert rows[0]["source_date"] == "2025.03.30"


def test_bars_with_null_volume_survive_a_parquet_round_trip(tmp_path: Path) -> None:
    frame = _frame([("2025.01.02", "09:30:00"), ("2025.01.02", "09:31:00")])
    table, _ = _convert(frame)
    index = table.schema.get_field_index("volume")
    nulled = table.set_column(index, "volume", pa.array([None, 10.0], type=pa.float64()))
    result = parquet_round_trip(nulled, tmp_path / "bars.parquet")
    assert result.rows == 2
    assert result.schema_equal
    assert result.values_equal
