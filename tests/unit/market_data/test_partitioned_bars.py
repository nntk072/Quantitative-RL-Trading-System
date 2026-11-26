"""Partitioned Parquet bars: idempotent publish, interruption safety and CSV parity (DATA-INGESTION)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest

from market_data import partitioned_bars as pb
from market_data.arrow_schemas import BAR_SCHEMA, mt5_export_to_bars

REPO = Path(__file__).resolve().parents[3]
EXAMPLE = REPO / "data" / "examples" / "US100.cash_M1_202412300105_202501020334.csv"
INSTRUMENT = "US100.cash"


def _publish(store: Path) -> pb.PublishedDataset:
    return pb.publish_bars_dataset(EXAMPLE, store, instrument_id=INSTRUMENT, timeframe="M1")


def _parquet_files(dataset: pb.PublishedDataset) -> list[Path]:
    return sorted(dataset.path.rglob("*.parquet"))


def _count_writes(monkeypatch: pytest.MonkeyPatch, fail_on: int | None = None) -> Callable[[], int]:
    real = pb.write_partition
    calls = {"n": 0}

    def writer(table: pa.Table, path: Path) -> None:
        calls["n"] += 1
        if calls["n"] == fail_on:
            raise RuntimeError("simulated interruption")
        real(table, path)

    monkeypatch.setattr(pb, "write_partition", writer)
    return lambda: calls["n"]


def test_rerun_on_identical_input_keeps_identity_and_partitions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _publish(tmp_path)
    files_before = _parquet_files(first)
    writes = _count_writes(monkeypatch)
    second = _publish(tmp_path)
    assert second.identity == first.identity
    assert second.path == first.path
    assert second.row_count == first.row_count == 2880
    assert writes() == 0
    assert _parquet_files(second) == files_before
    assert [entry.name for entry in tmp_path.iterdir()] == [first.identity]


def test_identity_is_sha256_of_manifest_contents(tmp_path: Path) -> None:
    dataset = _publish(tmp_path)
    manifest = (dataset.path / pb.MANIFEST_NAME).read_bytes()
    assert hashlib.sha256(manifest).hexdigest() == dataset.identity
    assert dataset.identity == dataset.path.name


def test_partitions_follow_logical_layout_with_utc_date(tmp_path: Path) -> None:
    dataset = _publish(tmp_path)
    files = _parquet_files(dataset)
    prefix = "source=mt5-export/instrument=US100.cash/event_kind=bar/date="
    for file in files:
        relative = file.relative_to(dataset.path).as_posix()
        assert relative.startswith(prefix) and relative.endswith("/part-0000.parquet")
        table = pq.read_table(file)
        assert table.schema.equals(BAR_SCHEMA)
        date = file.parent.name.removeprefix("date=")
        assert set(table.column("instrument_id").to_pylist()) == {INSTRUMENT}
        assert set(table.column("event_time").to_pandas().dt.strftime("%Y-%m-%d")) == {date}
    frame = pb.read_mt5_export(EXAMPLE)
    local = pd.to_datetime(frame["DATE"] + " " + frame["TIME"], format="%Y.%m.%d %H:%M:%S")
    utc_days = local.dt.tz_localize("Europe/Helsinki").dt.tz_convert("UTC").dt.strftime("%Y-%m-%d")
    assert len(files) == utc_days.nunique()


def test_interrupted_publish_leaves_no_published_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference = _publish(tmp_path / "reference").identity
    store = tmp_path / "store"
    _count_writes(monkeypatch, fail_on=3)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        _publish(store)
    assert list(store.iterdir()) == []

    monkeypatch.undo()
    resumed = _publish(store)
    assert resumed.identity == reference
    assert [entry.name for entry in store.iterdir()] == [reference]


def test_readback_reconciles_with_converted_table_and_csv(tmp_path: Path) -> None:
    dataset = _publish(tmp_path)
    readback = pa.concat_tables([pq.read_table(file) for file in _parquet_files(dataset)])
    expected, problems = mt5_export_to_bars(
        pb.read_mt5_export(EXAMPLE), instrument_id=INSTRUMENT, timeframe="M1"
    )
    assert problems == []
    assert readback.num_rows == expected.num_rows == 2880
    assert readback.equals(expected)

    frame = pb.read_mt5_export(EXAMPLE)
    assert readback.num_rows == len(frame)
    for column, source in (("open", "OPEN"), ("high", "HIGH"), ("low", "LOW"), ("close", "CLOSE")):
        assert readback.column(column).to_pylist() == [float(value) for value in frame[source]]
    local = pd.to_datetime(frame["DATE"] + " " + frame["TIME"], format="%Y.%m.%d %H:%M:%S")
    utc = local.dt.tz_localize("Europe/Helsinki").dt.tz_convert("UTC")
    assert readback.column("event_time").to_pylist() == [ts.to_pydatetime() for ts in utc]
    assert readback.column("source_sequence").to_pylist() == list(range(len(frame)))
