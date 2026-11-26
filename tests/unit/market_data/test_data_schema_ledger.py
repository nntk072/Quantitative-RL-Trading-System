"""DATA-SCHEMAS quality ledger generator: committed example, pre-2026 window exclusion, chronology guard."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[3]
GENERATOR = REPO / "planning" / "native_modernization" / "data_schemas" / "build_quality_ledger.py"
COMMITTED = REPO / "planning" / "native_modernization" / "data_schemas" / "quality_ledger.json"
EXAMPLE = REPO / "data" / "examples" / "US100.cash_M1_202412300105_202501020334.csv"
HEADER = "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>"


def _load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_quality_ledger", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_export(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join([HEADER, *lines]) + "\n", encoding="utf-8")
    return path


def _bar(date: str, time: str) -> str:
    return f"{date}\t{time}\t100.0\t101.0\t99.0\t100.5\t10\t0\t0"


def test_committed_example_ledger_regenerates_exactly() -> None:
    generator = _load_generator()
    ledger = generator.build_ledger(EXAMPLE)
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    # The Parquet library version is environment provenance, not a data fact.
    for version_key in ("pyarrow_version", "polars_version"):
        ledger["parquet_round_trip"].pop(version_key)
        committed["parquet_round_trip"].pop(version_key)
    assert ledger == committed
    assert committed["reconciliation"]["reconciles"] is True
    assert committed["reconciliation"]["source_rows"] == 2880


def test_window_excludes_rows_on_or_after_the_cutoff_without_parsing_them(tmp_path: Path) -> None:
    generator = _load_generator()
    source = _write_export(
        tmp_path / "export.csv",
        [
            _bar("2025.12.31", "09:30:00"),
            _bar("2025.12.31", "09:31:00"),
            # Rows dated 2026 are never parsed: a non-numeric price here would fail a parse.
            "2026.01.02\t09:30:00\tNOT_A_NUMBER\t101.0\t99.0\t100.5\t10\t0\t0",
            "2026.01.02\t09:31:00\tNOT_A_NUMBER\t101.0\t99.0\t100.5\t10\t0\t0",
        ],
    )
    ledger = generator.build_ledger(source, window_before="2026.01.01")
    assert ledger["window"]["rows_in_window"] == 2
    assert ledger["window"]["lines_on_or_after_cutoff"] == 2
    assert ledger["source"]["body_lines_in_file"] == 4
    assert ledger["window"]["last_source_label"] == "2025.12.31 09:31:00"
    assert ledger["reconciliation"]["reconciles"] is True
    assert "2026" not in json.dumps(ledger["window"]["first_source_label"])


def test_out_of_order_export_is_refused_for_a_prefix_window(tmp_path: Path) -> None:
    generator = _load_generator()
    source = _write_export(
        tmp_path / "unordered.csv",
        [
            _bar("2025.12.31", "09:30:00"),
            _bar("2026.01.02", "09:30:00"),
            _bar("2025.12.31", "09:31:00"),
        ],
    )
    with pytest.raises(RuntimeError, match="not chronological"):
        generator.build_ledger(source, window_before="2026.01.01")


def test_parquet_outputs_are_written_with_a_manifest(tmp_path: Path) -> None:
    generator = _load_generator()
    source = _write_export(tmp_path / "export.csv", [_bar("2025.01.02", "09:30:00")])
    out_dir = tmp_path / "outputs"
    ledger = generator.build_ledger(source, parquet_dir=out_dir)
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bars_rows"] == 1
    assert manifest["quarantine_rows"] == 0
    assert (out_dir / "bars.parquet").is_file()
    assert (out_dir / "quarantine.parquet").is_file()
    assert ledger["parquet_round_trip"]["values_equal"] is True
