from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from market_data.news.calendar import (
    blackout_mask,
    classify,
    events_from_ics,
    fomc_events,
    parse_ics,
    write_calendar,
)

SAMPLE_ICS = """BEGIN:VCALENDAR\r
BEGIN:VEVENT\r
SUMMARY:Employment Situation\r
DTSTART;TZID=America/New_York:20250207T083000\r
END:VEVENT\r
BEGIN:VEVENT\r
SUMMARY:Gross Domestic Product\\, 4th Quarter and Year 2024 (Advance Esti\r
 mate)\r
DTSTART;VALUE=DATE-TIME:20250130T133000Z\r
END:VEVENT\r
BEGIN:VEVENT\r
SUMMARY:Employment Situation of Veterans\r
DTSTART;TZID=America/New_York:20250328T100000\r
END:VEVENT\r
END:VCALENDAR\r
"""


def test_parse_ics_unfolds_lines_unescapes_and_converts_to_utc() -> None:
    events = parse_ics(SAMPLE_ICS)

    assert events[0] == (datetime(2025, 2, 7, 13, 30, tzinfo=UTC), "Employment Situation")
    assert events[1] == (
        datetime(2025, 1, 30, 13, 30, tzinfo=UTC),
        "Gross Domestic Product, 4th Quarter and Year 2024 (Advance Estimate)",
    )


def test_classify_keeps_headline_releases_only() -> None:
    assert classify("Employment Situation") == "NFP"
    assert classify("Real Earnings; CPI") == "CPI"
    assert classify("PPI") == "PPI"
    assert classify("JOLTS") == "JOLTS"
    assert classify("GDP (Advance Estimate), Q4 and Year 2025") == "GDP"
    assert classify("Personal Income and Outlays, December 2024") == "PCE"
    assert classify("Employment Situation of Veterans") is None
    assert classify("State JOLTS") is None
    assert classify("Real Earnings") is None
    assert classify("GDP by State and Personal Income by State") is None


def test_events_from_ics_records_source_hash(tmp_path: Path) -> None:
    path = tmp_path / "feed.ics"
    path.write_text(SAMPLE_ICS, encoding="utf-8")

    rows = events_from_ics(path, "test-source")

    assert [row.category for row in rows] == ["NFP", "GDP"]
    assert all(len(row.source_sha256) == 64 for row in rows)


def test_fomc_statement_time_follows_daylight_saving() -> None:
    rows = {row.utc_time.date(): row.utc_time for row in fomc_events()}

    # 14:00 New York time is 19:00 UTC in winter and 18:00 UTC in summer.
    assert rows[datetime(2025, 1, 29).date()] == datetime(2025, 1, 29, 19, tzinfo=UTC)
    assert rows[datetime(2025, 6, 18).date()] == datetime(2025, 6, 18, 18, tzinfo=UTC)


def test_blackout_window_is_inclusive_and_uses_bar_start() -> None:
    release = datetime(2025, 2, 7, 13, 30, tzinfo=UTC)
    bars = [
        datetime(2025, 2, 7, 13, 24, tzinfo=UTC),  # 6 min before: outside
        datetime(2025, 2, 7, 13, 25, tzinfo=UTC),  # exactly 5 min before: inside
        datetime(2025, 2, 7, 13, 30, tzinfo=UTC),  # at release: inside
        datetime(2025, 2, 7, 13, 35, tzinfo=UTC),  # exactly 5 min after: inside
        datetime(2025, 2, 7, 13, 36, tzinfo=UTC),  # 6 min after: outside
    ]

    mask = blackout_mask(bars, [release], minutes_before=5, minutes_after=5)

    assert mask == [False, True, True, True, False]


def test_write_calendar_sorts_rows_and_records_provenance(tmp_path: Path) -> None:
    events = fomc_events()[:2]
    out = tmp_path / "calendar.csv"

    count = write_calendar(list(reversed(events)), out, "2026-11-23")

    lines = out.read_text(encoding="utf-8").splitlines()
    assert count == 2
    assert lines[0].startswith("utc_time,category,summary")
    assert lines[1].startswith("2025-01-29T19:00:00Z,FOMC")
    assert lines[1].endswith(",2026-11-23")
