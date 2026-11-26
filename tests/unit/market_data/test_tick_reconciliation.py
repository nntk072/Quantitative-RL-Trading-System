"""Tick/quote export reconciliation: one-sided ticks, DST, crossed quotes, chunk boundaries, post-cutoff rows."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from market_data.arrow_schemas import QUOTE_SCHEMA
from market_data.tick_reconciliation import reconcile_tick_export, scan_tick_window

HEADER = "<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>"
ROWS = [
    "2025.01.02\t09:30:00.100\t100.00\t100.20\t\t\t6",  # kept
    "2025.01.02\t09:30:00.200\t\t100.25\t\t\t2",  # one-sided: bid missing -> explicit null, kept
    "2025.01.02\t09:30:01.000\t100.50\t100.10\t\t\t2",  # crossed quote -> quarantined
    "2025.03.30\t03:30:00.000\t100.00\t100.20\t\t\t6",  # spring-forward gap -> quarantined (DST)
    "2025.03.30\t04:30:00.000\t100.00\t100.20\t\t\t6",  # kept
    "2025.03.30\t04:31:00.000\t100.00\t100.20\t\t\t",  # empty FLAGS -> quarantined
    "2026.01.02\t09:30:00.000\tNOT_A_NUMBER\t100.20\t\t\t6",  # post-cutoff: never parsed
]


@pytest.fixture()
def export(tmp_path: Path) -> Path:
    path = tmp_path / "ticks.csv"
    path.write_text("\n".join([HEADER, *ROWS]) + "\n", encoding="utf-8", newline="")
    return path


def test_scan_counts_window_lines_and_hashes_the_whole_file(export: Path) -> None:
    scan = scan_tick_window(export, "2026.01.01")
    assert (scan.pre_lines, scan.post_lines, scan.body_lines) == (6, 1, 7)
    assert scan.sha256 == hashlib.sha256(export.read_bytes()).hexdigest()
    assert (scan.first_label, scan.last_label) == ("2025.01.02", "2025.03.30")


def test_scan_refuses_an_out_of_window_row_before_an_in_window_row(tmp_path: Path) -> None:
    path = tmp_path / "unordered.csv"
    path.write_text("\n".join([HEADER, ROWS[0], ROWS[-1], ROWS[1]]) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not chronological"):
        scan_tick_window(path, "2026.01.01")


def test_reconciliation_accounts_for_every_window_row_across_chunks(
    export: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    ledger = reconcile_tick_export(export, "2026.01.01", out, chunk_rows=2)
    rec = ledger["reconciliation"]
    assert rec["window_rows"] == 6
    assert rec["converted_rows"] == 3
    assert rec["quarantined_rows"] == 3
    assert rec["unexplained_rows"] == 0
    assert rec["oracle_event_mismatches"] == 0
    assert rec["oracle_dst_mismatches"] == 0
    assert rec["value_mismatches"] == 0
    assert rec["reconciles"] is True
    assert ledger["conversion"]["parts"] == 3


def test_quarantine_reasons_name_each_excluded_row(export: Path, tmp_path: Path) -> None:
    ledger = reconcile_tick_export(export, "2026.01.01", tmp_path / "out", chunk_rows=2)
    assert ledger["quarantine_by_reason"] == {
        "bid exceeds ask": 1,
        "nonexistent local time (DST spring-forward)": 1,
        "source_flags missing": 1,
    }


def test_one_sided_tick_is_kept_with_an_explicit_null_bid(export: Path, tmp_path: Path) -> None:
    reconcile_tick_export(export, "2026.01.01", tmp_path / "out", chunk_rows=2)
    parts = sorted((tmp_path / "out").glob("quotes_part_*.parquet"))
    table = pa.concat_tables([pq.read_table(p) for p in parts])
    assert table.schema.equals(QUOTE_SCHEMA)
    assert table.num_rows == 3
    assert table.column("bid").to_pylist() == [100.0, None, 100.0]
    assert table.column("ask").to_pylist() == [100.2, 100.25, 100.2]
    assert table.column("source_sequence").to_pylist() == [0, 1, 4]


def test_post_cutoff_row_is_counted_not_parsed(export: Path, tmp_path: Path) -> None:
    ledger = reconcile_tick_export(export, "2026.01.01", tmp_path / "out", chunk_rows=2)
    assert ledger["source"]["lines_on_or_after_cutoff"] == 1
    assert ledger["reconciliation"]["unexplained_rows"] == 0


def test_manifest_and_part_digests_match_the_files_written(export: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    ledger = reconcile_tick_export(export, "2026.01.01", out, chunk_rows=2)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["reconciliation"] == ledger["reconciliation"]
    for part in ledger["parquet"]["parts"]:
        path = out / f"quotes_part_{part['part']:04d}.parquet"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == part["quotes"]["sha256"]
        assert (
            part["quotes"]["pyarrow_round_trip_equal"] and part["quotes"]["polars_round_trip_equal"]
        )
    assert ledger["parquet"]["round_trip_all_parts_equal"] is True


def test_out_of_order_rows_inside_the_window_fail_reconciliation(tmp_path: Path) -> None:
    path = tmp_path / "unsorted.csv"
    path.write_text("\n".join([HEADER, ROWS[0], ROWS[4], ROWS[1]]) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="tick reconciliation failed"):
        reconcile_tick_export(path, "2026.01.01", tmp_path / "out", chunk_rows=2)
