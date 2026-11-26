"""Higher-timeframe export vs resampled M1 reconciliation, and the pre-cutoff export window (DATA-SCHEMAS)."""

from __future__ import annotations

import io
from datetime import UTC

import numpy as np
import pandas as pd
import pytest

from market_data.export_window import split_export_window, window_frame
from market_data.timeframe_reconciliation import (
    compare_export_to_resampled,
    export_frame,
    m1_frame,
    resample_m1,
)

HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"


def _m1(rows: list[tuple[str, float, float, float, float, float]]) -> pd.DataFrame:
    """Build an M1 frame from (utc_iso, open, high, low, close, volume) tuples."""
    utc = pd.DatetimeIndex([pd.Timestamp(r[0], tz=UTC) for r in rows])
    return m1_frame(
        utc,
        {
            "open": np.array([r[1] for r in rows], dtype=np.float64),
            "high": np.array([r[2] for r in rows], dtype=np.float64),
            "low": np.array([r[3] for r in rows], dtype=np.float64),
            "close": np.array([r[4] for r in rows], dtype=np.float64),
            "volume": np.array([r[5] for r in rows], dtype=np.float64),
        },
    )


def _bars_from_m1(start_utc: str, minutes: int) -> pd.DataFrame:
    base = pd.Timestamp(start_utc, tz=UTC)
    rng = np.random.default_rng(3)
    close = 100 + np.cumsum(rng.normal(0, 0.2, minutes))
    utc = pd.DatetimeIndex([base + pd.Timedelta(minutes=i) for i in range(minutes)])
    return m1_frame(
        utc,
        {
            "open": close - 0.05,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": rng.integers(1, 20, minutes).astype(float),
        },
    )


def _export_text(rows: list[str]) -> str:
    return "\n".join([HEADER, *rows]) + "\n"


def test_resampled_m3_buckets_align_to_local_wall_clock_and_aggregate_ohlc() -> None:
    m1 = _m1(
        [
            ("2025-01-02 07:03:00", 10.0, 12.0, 9.0, 11.0, 5.0),  # 09:03 Helsinki
            ("2025-01-02 07:04:00", 11.0, 14.0, 10.0, 13.0, 7.0),
            ("2025-01-02 07:05:00", 13.0, 13.5, 8.0, 9.0, 4.0),
        ]
    )
    bars = resample_m1(m1, "M3")
    assert list(pd.DatetimeIndex(bars.index).strftime("%H:%M")) == ["09:03"]
    row = bars.iloc[0]
    assert (row["open"], row["high"], row["low"], row["close"]) == (10.0, 14.0, 8.0, 9.0)
    assert row["volume"] == 16.0
    assert row["m1_count"] == 3


def test_daily_export_without_time_column_opens_at_local_midnight() -> None:
    frame = pd.read_csv(
        io.StringIO(
            "<DATE>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n2025.01.02\t1\t2\t0.5\t1.5\t9\t0\t1\n"
        ),
        sep="\t",
        dtype=str,
    ).rename(columns=lambda n: n.strip("<>"))
    export = export_frame(frame)
    assert export.index[0].strftime("%Y-%m-%d %H:%M") == "2025-01-02 00:00"


def test_every_bucket_matching_is_reported_with_zero_mismatches() -> None:
    m1 = _bars_from_m1("2025-01-02 07:00", 60)
    resampled = resample_m1(m1, "M15")
    export = resampled[["open", "high", "low", "close", "volume"]].copy()
    result = compare_export_to_resampled(export, resampled, m1.index.min())
    assert result["matched_buckets"] == len(resampled) == 4
    assert result["matched_with_all_fields_equal"] == 4
    assert result["export_only_buckets"] == 0 and result["resampled_only_buckets"] == 0
    assert result["max_abs_price_delta"] == 0.0


def test_a_single_wrong_high_is_counted_on_its_field_with_its_label() -> None:
    m1 = _bars_from_m1("2025-01-02 07:00", 60)
    resampled = resample_m1(m1, "H1")
    export = resampled[["open", "high", "low", "close", "volume"]].copy()
    highs = export["high"].to_numpy(copy=True)
    highs[0] += 0.25
    export["high"] = highs
    result = compare_export_to_resampled(export, resampled, m1.index.min())
    assert result["field_mismatch_counts"]["high"] == 1
    assert result["matched_with_any_field_mismatch"] == 1
    assert result["max_abs_price_delta"] == pytest.approx(0.25)
    assert result["first_mismatch_local_opens"] == ["2025-01-02 09:00"]


def test_export_only_and_resampled_only_buckets_are_accounted_for() -> None:
    m1 = _bars_from_m1("2025-01-02 07:00", 180)
    resampled = resample_m1(m1, "H1")
    # Drop the last resampled bucket from the export and add one bucket that M1 does not cover.
    export = resampled[["open", "high", "low", "close", "volume"]].iloc[:-1].copy()
    export.loc[export.index[-1] + pd.Timedelta(hours=5)] = [1.0, 1.0, 1.0, 1.0, 1.0]
    result = compare_export_to_resampled(export, resampled, m1.index.min())
    assert result["export_only_buckets"] == 1
    assert result["resampled_only_buckets"] == 1
    assert result["matched_buckets"] == len(resampled) - 1


def test_first_bucket_opening_before_the_first_m1_bar_is_counted_as_window_edge() -> None:
    m1 = _bars_from_m1(
        "2025-01-02 07:05", 40
    )  # first M1 bar at 09:05 local, inside the 09:00 bucket
    resampled = resample_m1(m1, "M30")
    export = resampled[["open", "high", "low", "close", "volume"]].copy()
    result = compare_export_to_resampled(export, resampled, m1.index.min())
    assert result["window_edge_partial_matched"] == 1


def test_unsupported_timeframe_is_refused() -> None:
    with pytest.raises(ValueError, match="unsupported timeframe"):
        resample_m1(_bars_from_m1("2025-01-02 07:00", 5), "M7")


def test_split_drops_post_cutoff_values_without_parsing_them() -> None:
    raw = _export_text(
        [
            "2025.12.31\t09:30:00\t1\t2\t0.5\t1.5\t9\t0\t1",
            "2026.01.02\t09:30:00\tNOT_A_NUMBER\t2\t0.5\t1.5\t9\t0\t1",
        ]
    ).encode("ascii")
    window = split_export_window(raw, "2026.01.01")
    assert window.lines_on_or_after_cutoff == 1
    assert window.body_lines_in_file == 2
    assert len(window_frame(window)) == 1


def test_split_refuses_a_non_chronological_export() -> None:
    raw = _export_text(
        [
            "2025.12.31\t09:30:00\t1\t2\t0.5\t1.5\t9\t0\t1",
            "2026.01.02\t09:30:00\t1\t2\t0.5\t1.5\t9\t0\t1",
            "2025.12.31\t09:31:00\t1\t2\t0.5\t1.5\t9\t0\t1",
        ]
    ).encode("ascii")
    with pytest.raises(RuntimeError, match="not chronological"):
        split_export_window(raw, "2026.01.01")


def test_split_without_cutoff_keeps_every_line() -> None:
    raw = _export_text(["2025.12.31\t09:30:00\t1\t2\t0.5\t1.5\t9\t0\t1"]).encode("ascii")
    window = split_export_window(raw, None)
    assert (window.lines_on_or_after_cutoff, window.body_lines_in_file) == (0, 1)
