"""Unit checks for configured native-versus-derived timeframe comparisons."""

from __future__ import annotations

import pandas as pd
from scripts.research.analysis.market_data.compare_configured_timeframe_bars import (
    availability_summary,
    compare_bar_frames,
    compare_spread_aggregations,
    source_row_coverage_summary,
)


def _bars(index: pd.DatetimeIndex, closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100.0] * len(index),
            "high": [101.0] * len(index),
            "low": [99.0] * len(index),
            "close": closes,
        },
        index=index,
    )


def test_native_derived_comparison_reports_exact_parity() -> None:
    """Identical rows and values produce a zero-difference report."""
    index = pd.date_range("2025-01-02 09:00", periods=2, freq="3min", tz="Etc/GMT-3")

    result = compare_bar_frames(
        _bars(index, [100.5, 100.75]),
        _bars(index, [100.5, 100.75]),
        columns=("open", "high", "low", "close"),
    )

    assert result["common_timestamp_rows"] == 2
    assert result["derived_timestamps_missing_native"] == 0
    assert result["native_timestamps_missing_derived"] == 0
    assert result["field_comparisons"]["close"]["mismatch_rows"] == 0


def test_native_derived_comparison_separates_timestamp_and_value_gaps() -> None:
    """Missing timestamps and numeric disagreements remain independently visible."""
    native_index = pd.date_range("2025-01-02 09:00", periods=2, freq="3min", tz="Etc/GMT-3")
    derived_index = native_index + pd.Timedelta(minutes=3)

    result = compare_bar_frames(
        _bars(native_index, [100.5, 100.75]),
        _bars(derived_index, [100.6, 100.75]),
        columns=("open", "high", "low", "close"),
    )

    assert result["common_timestamp_rows"] == 1
    assert result["derived_timestamps_missing_native"] == 1
    assert result["native_timestamps_missing_derived"] == 1
    assert result["field_comparisons"]["close"]["mismatch_rows"] == 1


def test_availability_uses_first_m1_at_or_after_higher_bar_close() -> None:
    """A missing close-time M1 row is reported as a measured availability delay."""
    timezone = "Etc/GMT-3"
    higher_index = pd.DatetimeIndex(["2025-01-02 09:00", "2025-01-02 09:03"], tz=timezone)
    m1_index = pd.DatetimeIndex(["2025-01-02 09:03", "2025-01-02 09:07"], tz=timezone)
    higher = _bars(higher_index, [100.5, 100.75])
    m1 = _bars(m1_index, [100.5, 100.75])

    summary = availability_summary(m1, higher, "M3", scheduled_closes={}, session_start="16:30")

    assert summary["rows_first_visible_exactly_at_close"] == 1
    assert summary["rows_first_visible_after_close"] == 1
    assert summary["max_first_m1_delay_seconds"] == 60.0


def test_native_spread_last_value_is_distinguished_from_m1_mean() -> None:
    """Native spread can match the last M1 quote while differing from M1 mean."""
    timezone = "Etc/GMT-3"
    index = pd.date_range("2025-01-02 09:00", periods=3, freq="min", tz=timezone)
    m1 = pd.DataFrame({"spread": [1.0, 2.0, 3.0]}, index=index)
    native_index = pd.DatetimeIndex([index[0]])
    native = pd.DataFrame({"spread": [3.0]}, index=native_index)

    comparison = compare_spread_aggregations(native, m1, "M3")

    assert comparison["status"] == "matches_m1_last"
    assert comparison["m1_mean_vs_native"]["mismatch_rows"] == 1
    assert comparison["m1_last_vs_native"]["mismatch_rows"] == 0


def test_source_row_coverage_reports_partial_and_empty_m1_bins() -> None:
    """Coverage is measured against each bar's local minute grid, not treated as data loss."""
    timezone = "Etc/GMT-3"
    higher_index = pd.DatetimeIndex(
        ["2025-01-02 09:00", "2025-01-02 09:03", "2025-01-02 09:06"], tz=timezone
    )
    m1_index = pd.DatetimeIndex(
        ["2025-01-02 09:00", "2025-01-02 09:02", "2025-01-02 09:06"], tz=timezone
    )

    summary = source_row_coverage_summary(
        _bars(m1_index, [100.0, 100.2, 100.6]),
        _bars(higher_index, [100.2, 100.4, 100.6]),
        "M3",
        scheduled_closes={},
        session_start="16:30",
    )

    assert summary["expected_m1_grid_rows"] == 9
    assert summary["observed_m1_rows"] == 3
    assert summary["bars_with_fewer_rows_than_grid"] == 3
    assert summary["bars_with_zero_observed_rows"] == 1
    assert summary["first_incomplete_bar_timestamp"] == higher_index[0].isoformat()
