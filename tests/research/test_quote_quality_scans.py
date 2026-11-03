"""Fixture tests for reusable bounded market-data quality scanners."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
from scripts.research.analysis.market_data.quote_quality_scans import (
    load_m1_minutes,
    scan_tick_file,
)


def _write_tsv(path: Path, header: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> None:
    content = "\t".join(header) + "\n"
    content += "".join("\t".join(row) + "\n" for row in rows)
    path.write_text(content, encoding="utf-8")


def test_scan_tick_file_counts_quality_and_usable_quote_minutes(tmp_path: Path) -> None:
    """Tick scanner separates malformed, nonfinite, crossed and locked quotes."""
    path = tmp_path / "ticks.csv"
    _write_tsv(
        path,
        ("<DATE>", "<TIME>", "<BID>", "<ASK>"),
        (
            ("2025.01.06", "09:00:00.000", "100.0", "101.0"),
            ("2025.01.06", "09:00:00.000", "100.0", "100.0"),
            ("2025.01.06", "09:01:00.000", "101.0", "100.0"),
            ("bad-date", "09:02:00.000", "100.0", "101.0"),
            ("2025.01.06", "09:03:00.000", "", "101.0"),
        ),
    )
    expected_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    report = scan_tick_file(path, expected_hash)

    assert report["rows"] == 5
    assert report["invalid_timestamp_rows"] == 1
    assert report["nonfinite_bid_ask_rows"] == 1
    assert report["crossed_quote_rows_ask_below_bid"] == 1
    assert report["locked_quote_rows_ask_equals_bid"] == 1
    assert report["raw_order_breaks"] == 0
    assert report["adjacent_duplicate_timestamp_rows"] == 1
    assert report["experiment_run_hash_match"] is True
    observed_minutes = report.pop("_observed_m1_minutes")
    assert observed_minutes == {
        int(pd.Timestamp("2025-01-06 09:00:00").value // 60_000_000_000),
    }


def test_scan_tick_file_records_hash_mismatch_and_order_breaks(tmp_path: Path) -> None:
    """The audit result retains exact input mismatch and descending time count."""
    path = tmp_path / "ticks.csv"
    _write_tsv(
        path,
        ("<DATE>", "<TIME>", "<BID>", "<ASK>"),
        (
            ("2025.01.06", "09:01:00.000", "100.0", "101.0"),
            ("2025.01.06", "09:00:00.000", "100.0", "101.0"),
        ),
    )

    report = scan_tick_file(path, "not-the-current-hash")

    assert report["raw_order_breaks"] == 1
    assert report["experiment_run_hash_match"] is False
    assert report["experiment_run_expected_sha256"] == "not-the-current-hash"


def test_load_m1_minutes_ignores_unparseable_timestamps(tmp_path: Path) -> None:
    """M1 coverage uses valid source bar starts and deduplicates the minute key."""
    path = tmp_path / "bars.csv"
    _write_tsv(
        path,
        ("<DATE>", "<TIME>"),
        (
            ("2025.01.06", "09:00:00"),
            ("2025.01.06", "09:00:30"),
            ("2025.01.06", "09:01:00"),
            ("bad-date", "09:02:00"),
        ),
    )

    minutes = load_m1_minutes(path)

    assert minutes == {
        int(pd.Timestamp("2025-01-06 09:00:00").value // 60_000_000_000),
        int(pd.Timestamp("2025-01-06 09:01:00").value // 60_000_000_000),
    }
