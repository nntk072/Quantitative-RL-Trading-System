from __future__ import annotations

import pandas as pd
import pytest

from evaluation.candidate_quote_coverage import CandidateQuoteCoverage


def _coverage(tmp_path, values: list[bool]) -> CandidateQuoteCoverage:
    path = tmp_path / "coverage.csv"
    pd.DataFrame(
        {
            "bar_open_source_wall_clock": pd.date_range(
                "2025-01-02 16:00", periods=len(values), freq="min"
            ),
            "quote_complete": values,
        }
    ).to_csv(path, index=False)
    return CandidateQuoteCoverage.from_csv(path, timezone="Etc/GMT-3")


def test_first_incomplete_minute_is_timezone_converted(tmp_path) -> None:
    coverage = _coverage(tmp_path, [True, False, True])

    first_gap = coverage.first_incomplete_minute("2025-01-02T13:00:00Z", "2025-01-02T13:03:00Z")

    assert first_gap == pd.Timestamp("2025-01-02T13:01:00Z")


def test_complete_half_open_interval_ignores_gap_at_end(tmp_path) -> None:
    coverage = _coverage(tmp_path, [True, False, True])

    assert coverage.first_incomplete_minute("2025-01-02T13:00:00Z", "2025-01-02T13:01:00Z") is None


def test_partial_minute_interval_includes_the_touched_minute(tmp_path) -> None:
    coverage = _coverage(tmp_path, [True, False, True])

    first_gap = coverage.first_incomplete_minute("2025-01-02T13:00:30Z", "2025-01-02T13:01:30Z")

    assert first_gap == pd.Timestamp("2025-01-02T13:01:00Z")


def test_bad_minute_containing_an_intraminute_entry_never_predates_entry(tmp_path) -> None:
    coverage = _coverage(tmp_path, [False, True, True])
    start = pd.Timestamp("2025-01-02T13:00:30Z")
    assert coverage.first_incomplete_minute(start, "2025-01-02T13:01:30Z") == start
    assert (
        coverage.first_incomplete_minute("2025-01-02T15:00:30+02:00", "2025-01-02T15:01:30+02:00")
        == start
    )
    assert coverage.first_incomplete_minute(
        "2025-01-02T12:59:30Z", "2025-01-02T13:00:30Z"
    ) == pd.Timestamp("2025-01-02T12:59:30Z")


def test_missing_minutes_and_out_of_range_data_fail_closed(tmp_path) -> None:
    path = tmp_path / "coverage.csv"
    pd.DataFrame(
        {
            "bar_open_source_wall_clock": pd.to_datetime(["2025-01-02 16:00", "2025-01-02 16:02"]),
            "quote_complete": [True, True],
        }
    ).to_csv(path, index=False)
    coverage = CandidateQuoteCoverage.from_csv(path, timezone="Etc/GMT-3")

    assert coverage.first_incomplete_minute(
        "2025-01-02T13:00:00Z", "2025-01-02T13:03:00Z"
    ) == pd.Timestamp("2025-01-02T13:01:00Z")
    assert coverage.first_incomplete_minute(
        "2025-01-02T12:59:00Z", "2025-01-02T13:00:00Z"
    ) == pd.Timestamp("2025-01-02T12:59:00Z")


def test_interval_bounds_must_be_timezone_aware(tmp_path) -> None:
    coverage = _coverage(tmp_path, [True, True])

    with pytest.raises(ValueError, match="timezone-aware"):
        coverage.first_incomplete_minute("2025-01-02 16:00:00", "2025-01-02 16:01:00")
