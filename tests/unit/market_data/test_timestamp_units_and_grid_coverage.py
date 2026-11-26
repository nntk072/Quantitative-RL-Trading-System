"""Declared timestamp units, grid gaps and off-grid rows, and calendar classification of gaps (DATA-SCHEMAS)."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pyarrow as pa  # type: ignore[import-untyped]
import pytest

from market_data.arrow_schemas import CALENDAR_SCHEMA, CALENDAR_SCHEMA_ID, epoch_to_utc_ns
from market_data.coverage import CALENDAR_CLOSED, UNCLASSIFIED, UNEXPLAINED, grid_report

MINUTE_NS = 60 * 1_000_000_000
T0 = datetime(2025, 1, 2, 9, 0, tzinfo=UTC)


def _ns(hour: int, minute: int = 0) -> int:
    return int(datetime(2025, 1, 2, hour, minute, tzinfo=UTC).timestamp()) * 1_000_000_000


def _calendar(*sessions: tuple[datetime, datetime, str]) -> pa.Table:
    rows = [
        {
            "instrument_id": "US100.cash",
            "session_open": open_,
            "session_close": close,
            "session_kind": kind,
            "source_id": "registry",
            "schema_id": CALENDAR_SCHEMA_ID,
        }
        for open_, close, kind in sessions
    ]
    return pa.Table.from_pylist(rows, schema=CALENDAR_SCHEMA)


def test_epoch_seconds_milliseconds_and_microseconds_convert_to_utc_nanoseconds() -> None:
    seconds = np.array([1_735_808_400], dtype=np.int64)
    assert epoch_to_utc_ns(seconds, "s")[0] == 1_735_808_400 * 1_000_000_000
    assert epoch_to_utc_ns(seconds * 1000, "ms")[0] == 1_735_808_400 * 1_000_000_000
    assert epoch_to_utc_ns(seconds * 1_000_000, "us")[0] == 1_735_808_400 * 1_000_000_000
    assert epoch_to_utc_ns(seconds * 1_000_000_000, "ns")[0] == 1_735_808_400 * 1_000_000_000


def test_milliseconds_declared_as_nanoseconds_are_refused_not_read_as_1970() -> None:
    milliseconds = np.array([1_735_808_400_000], dtype=np.int64)
    with pytest.raises(ValueError, match="declared unit is probably wrong"):
        epoch_to_utc_ns(milliseconds, "ns")


def test_seconds_declared_as_milliseconds_are_refused() -> None:
    with pytest.raises(ValueError, match="declared unit is probably wrong"):
        epoch_to_utc_ns(np.array([1_735_808_400], dtype=np.int64), "ms")


def test_unknown_unit_and_empty_input_are_handled_explicitly() -> None:
    with pytest.raises(ValueError, match="unknown timestamp unit"):
        epoch_to_utc_ns(np.array([1], dtype=np.int64), "minutes")
    assert epoch_to_utc_ns(np.array([], dtype=np.int64), "ms").size == 0


def test_consecutive_minute_bars_have_no_gap() -> None:
    event = np.array([_ns(9, m) for m in range(5)], dtype=np.int64)
    report = grid_report(event, MINUTE_NS)
    assert report.gaps == []
    assert report.off_grid_rows == []
    assert report.rows == 5


def test_a_three_minute_hole_is_one_gap_with_two_missing_slots_and_no_calendar_claim() -> None:
    event = np.array([_ns(9, 0), _ns(9, 1), _ns(9, 4)], dtype=np.int64)
    report = grid_report(event, MINUTE_NS)
    assert [(g.missing_slots, g.status) for g in report.gaps] == [(2, UNCLASSIFIED)]
    assert report.gaps[0].reason == "no authoritative session calendar supplied"
    assert report.missing_slots == 2


def test_a_bar_off_the_minute_grid_is_reported_by_row() -> None:
    event = np.array([_ns(9, 0), _ns(9, 1) + 30 * 1_000_000_000, _ns(9, 2)], dtype=np.int64)
    report = grid_report(event, MINUTE_NS)
    assert report.off_grid_rows == [1]


def test_a_daily_grid_anchored_at_a_session_open_is_not_off_grid() -> None:
    session_open = _ns(22, 0)
    day = 24 * 60 * MINUTE_NS
    event = np.array([session_open, session_open + day], dtype=np.int64)
    report = grid_report(event, day, origin_ns=session_open)
    assert report.off_grid_rows == []
    assert report.gaps == []


def test_an_off_grid_interval_longer_than_one_step_still_has_a_missing_slot() -> None:
    event = np.array(
        [_ns(9, 0) + 10 * 1_000_000_000, _ns(9, 1) + 50 * 1_000_000_000], dtype=np.int64
    )
    report = grid_report(event, MINUTE_NS)
    assert [g.missing_slots for g in report.gaps] == [1]
    assert report.off_grid_rows == [0, 1]


def test_gap_inside_a_calendar_closure_is_calendar_closed() -> None:
    event = np.array([_ns(9, 0), _ns(9, 4)], dtype=np.int64)
    calendar = _calendar(
        (datetime(2025, 1, 2, 8, 0, tzinfo=UTC), datetime(2025, 1, 2, 10, 0, tzinfo=UTC), "closed")
    )
    report = grid_report(event, MINUTE_NS, calendar=calendar)
    assert [(g.missing_slots, g.status) for g in report.gaps] == [(3, CALENDAR_CLOSED)]


def test_gap_overlapping_a_trading_session_is_unexplained() -> None:
    event = np.array([_ns(9, 0), _ns(9, 4)], dtype=np.int64)
    calendar = _calendar(
        (datetime(2025, 1, 2, 8, 0, tzinfo=UTC), datetime(2025, 1, 2, 10, 0, tzinfo=UTC), "trading")
    )
    report = grid_report(event, MINUTE_NS, calendar=calendar)
    assert [(g.missing_slots, g.status) for g in report.gaps] == [(3, UNEXPLAINED)]


def test_partial_calendar_coverage_leaves_the_gap_unclassified() -> None:
    event = np.array([_ns(9, 0), _ns(9, 4)], dtype=np.int64)
    calendar = _calendar(
        (datetime(2025, 1, 2, 8, 0, tzinfo=UTC), datetime(2025, 1, 2, 9, 2, tzinfo=UTC), "closed")
    )
    report = grid_report(event, MINUTE_NS, calendar=calendar)
    assert [g.status for g in report.gaps] == [UNCLASSIFIED]
    assert report.gaps[0].reason == "session calendar does not cover the missing interval"


def test_calendar_closure_split_into_two_sessions_still_covers_the_gap() -> None:
    event = np.array([_ns(9, 0), _ns(9, 4)], dtype=np.int64)
    calendar = _calendar(
        (datetime(2025, 1, 2, 8, 0, tzinfo=UTC), datetime(2025, 1, 2, 9, 2, tzinfo=UTC), "closed"),
        (datetime(2025, 1, 2, 9, 2, tzinfo=UTC), datetime(2025, 1, 2, 10, 0, tzinfo=UTC), "closed"),
    )
    report = grid_report(event, MINUTE_NS, calendar=calendar)
    assert [g.status for g in report.gaps] == [CALENDAR_CLOSED]


def test_grid_report_refuses_unordered_or_duplicate_event_times() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        grid_report(np.array([_ns(9, 1), _ns(9, 0)], dtype=np.int64), MINUTE_NS)
    with pytest.raises(ValueError, match="strictly increasing"):
        grid_report(np.array([_ns(9, 0), _ns(9, 0)], dtype=np.int64), MINUTE_NS)


def test_grid_report_refuses_an_invalid_calendar_and_a_non_positive_grid() -> None:
    invalid = _calendar(
        (datetime(2025, 1, 2, 10, 0, tzinfo=UTC), datetime(2025, 1, 2, 9, 0, tzinfo=UTC), "closed")
    )
    with pytest.raises(ValueError, match="invalid session calendar"):
        grid_report(np.array([_ns(9, 0)], dtype=np.int64), MINUTE_NS, calendar=invalid)
    with pytest.raises(ValueError, match="grid spacing must be positive"):
        grid_report(np.array([_ns(9, 0)], dtype=np.int64), 0)
