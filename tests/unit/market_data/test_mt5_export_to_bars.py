"""MT5 chart export to normalized UTC bars: clock, DST and reconciliation (DATA-SCHEMAS)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from market_data.arrow_schemas import BAR_SCHEMA, mt5_export_to_bars

REPO = Path(__file__).resolve().parents[3]
EXAMPLE = REPO / "data" / "examples" / "US100.cash_M1_202412300105_202501020334.csv"


def _read_export(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", dtype=str).rename(columns=lambda name: name.strip("<>"))


def _frame(rows: list[tuple[str, str]]) -> pd.DataFrame:
    """Build a one-minute export frame from (date, time) labels with flat prices."""
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


def test_example_export_converts_every_row_with_no_problems() -> None:
    frame = _read_export(EXAMPLE)
    table, problems = mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")
    assert table.schema.equals(BAR_SCHEMA)
    assert table.num_rows == len(frame) == 2880
    assert problems == []


def test_first_bar_is_helsinki_winter_time_converted_to_utc() -> None:
    # 2024-12-30 01:05 Helsinki is EET (UTC+2) -> 2024-12-29 23:05 UTC
    frame = _read_export(EXAMPLE)
    table, _ = mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")
    assert table.column("event_time")[0].as_py() == datetime(2024, 12, 29, 23, 5, tzinfo=UTC)
    assert table.column("close_time")[0].as_py() == datetime(2024, 12, 29, 23, 6, tzinfo=UTC)
    assert table.column("available_at")[0].as_py() == table.column("close_time")[0].as_py()


def test_prices_and_sequence_match_the_source_exactly() -> None:
    frame = _read_export(EXAMPLE)
    table, _ = mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")
    assert table.column("open")[0].as_py() == float(frame["OPEN"].iloc[0])
    assert table.column("close")[5].as_py() == float(frame["CLOSE"].iloc[5])
    assert table.column("source_sequence").to_pylist() == list(range(len(frame)))


def test_spring_forward_gap_is_reported_not_guessed() -> None:
    # 2025-03-30 03:00 -> 04:00 Helsinki; 03:30 does not exist.
    frame = _frame([("2025.03.30", "03:30:00"), ("2025.03.30", "04:30:00")])
    table, problems = mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")
    assert [(p.row, p.reason) for p in problems] == [
        (0, "nonexistent local time (DST spring-forward)")
    ]
    assert table.num_rows == 1
    # 04:30 EEST (UTC+3) -> 01:30 UTC
    assert table.column("event_time")[0].as_py() == datetime(2025, 3, 30, 1, 30, tzinfo=UTC)


def test_fall_back_repeated_hour_is_reported_not_guessed() -> None:
    # 2025-10-26 04:00 EEST -> 03:00 EET, so local 03:30 happens twice.
    frame = _frame([("2025.10.26", "03:30:00"), ("2025.10.26", "04:30:00")])
    table, problems = mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")
    assert [(p.row, p.reason) for p in problems] == [(0, "ambiguous local time (DST fall-back)")]
    # 04:30 EET (UTC+2) -> 02:30 UTC
    assert table.column("event_time")[0].as_py() == datetime(2025, 10, 26, 2, 30, tzinfo=UTC)


def test_ohlc_violation_is_reported_against_the_source_row() -> None:
    frame = _frame([("2025.01.02", "09:30:00"), ("2025.01.02", "09:31:00")])
    frame.loc[1, "HIGH"] = "100.0"  # high below close 100.5
    table, problems = mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")
    assert [(p.row, p.reason) for p in problems] == [(1, "OHLC bounds violated")]
    assert table.num_rows == 2


def test_unsupported_timeframe_is_refused() -> None:
    with pytest.raises(ValueError, match="unsupported native timeframe"):
        mt5_export_to_bars(_frame([("2025.01.02", "09:30:00")]), instrument_id="X", timeframe="M7")


def test_reconciliation_counts_match_the_source() -> None:
    frame = _read_export(EXAMPLE)
    table, problems = mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")
    rejected = {p.row for p in problems}
    assert table.num_rows + len(rejected) == len(frame)
    assert float(frame["CLOSE"].astype(float).sum()) == pytest.approx(
        sum(table.column("close").to_pylist())
        + sum(float(frame["CLOSE"].iloc[i]) for i in rejected)
    )
