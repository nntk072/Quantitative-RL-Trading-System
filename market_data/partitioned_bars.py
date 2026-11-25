"""Partitioned Parquet publish for normalized MT5 bars (DATA-INGESTION, offline part).

Partitions are ``source/instrument/event_kind/date`` (``date`` = UTC day of ``event_time``). The
dataset is staged in a temporary directory inside the store and published by one atomic rename.
Its identity is the SHA-256 of the canonical manifest, so reruns on identical input resolve to the
same directory. An interrupted publish leaves no published directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from artifacts.atomic import write_text_atomic
from market_data.arrow_schemas import SCHEMA_VERSION, mt5_export_to_bars

LAYOUT_VERSION = "partitioned-bars.v1"
MANIFEST_NAME = "_manifest.json"
_NS_PER_DAY = 86_400 * 1_000_000_000


@dataclass(frozen=True, slots=True)
class PublishedDataset:
    """A published dataset directory, its identity and its total row count."""

    path: Path
    identity: str
    row_count: int


def read_mt5_export(path: Path) -> pd.DataFrame:
    """Read a tab-separated MT5 chart export with bracketed header names stripped."""
    return pd.read_csv(path, sep="\t", dtype=str).rename(columns=lambda name: name.strip("<>"))


def write_partition(table: pa.Table, path: Path) -> None:
    """Write one partition file; the only write hook, replaced by tests to inject faults."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ipc_bytes(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    payload: bytes = sink.getvalue().to_pybytes()
    return payload


def _partitions(
    table: pa.Table, source_id: str, instrument_id: str, event_kind: str
) -> list[tuple[str, pa.Table]]:
    """Split rows into ``(relative path, partition table)`` pairs ordered by UTC date."""
    days = table.column("event_time").cast(pa.int64()).to_numpy() // _NS_PER_DAY
    parts: list[tuple[str, pa.Table]] = []
    for day in np.unique(days):
        date = np.datetime64(int(day), "D").astype(str)
        relative = (
            f"source={source_id}/instrument={instrument_id}/event_kind={event_kind}/date={date}"
            "/part-0000.parquet"
        )
        parts.append((relative, table.filter(pa.array(days == day))))
    return parts


def _canonical_manifest(
    *,
    source_sha256: str,
    source_id: str,
    instrument_id: str,
    event_kind: str,
    partitions: list[tuple[str, pa.Table]],
) -> str:
    entries = [
        {"path": rel, "row_count": part.num_rows, "content_sha256": _sha256(_ipc_bytes(part))}
        for rel, part in partitions
    ]
    entries.sort(key=lambda entry: entry["path"])
    manifest: dict[str, Any] = {
        "layout": LAYOUT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "source_sha256": source_sha256,
        "source_id": source_id,
        "instrument_id": instrument_id,
        "event_kind": event_kind,
        "row_count": sum(entry["row_count"] for entry in entries),
        "partitions": entries,
    }
    return json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"


def publish_bars_dataset(
    csv_path: Path,
    store: Path,
    *,
    instrument_id: str,
    timeframe: str,
    source_id: str = "mt5-export",
    event_kind: str = "bar",
) -> PublishedDataset:
    """Convert an MT5 chart export and publish it as an identity-named partitioned dataset.

    Raises:
        ValueError: If any row fails bar validation (the publish fails closed).
    """
    with csv_path.open("rb") as handle:
        source_sha256 = hashlib.file_digest(handle, "sha256").hexdigest()
    table, problems = mt5_export_to_bars(
        read_mt5_export(csv_path),
        instrument_id=instrument_id,
        timeframe=timeframe,
        source_id=source_id,
    )
    if problems:
        raise ValueError(f"{len(problems)} rows failed bar validation; first: {problems[0]}")
    partitions = _partitions(table, source_id, instrument_id, event_kind)
    text = _canonical_manifest(
        source_sha256=source_sha256,
        source_id=source_id,
        instrument_id=instrument_id,
        event_kind=event_kind,
        partitions=partitions,
    )
    identity = _sha256(text.encode("utf-8"))
    store.mkdir(parents=True, exist_ok=True)
    final = store / identity
    if final.exists():
        return PublishedDataset(final, identity, table.num_rows)

    staging = Path(tempfile.mkdtemp(prefix=f".{identity}.", suffix=".partial", dir=store))
    try:
        for relative, part in partitions:
            write_partition(part, staging / relative)
        write_text_atomic(staging / MANIFEST_NAME, text)
        os.rename(staging, final)
    except OSError:
        if not final.exists():
            raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return PublishedDataset(final, identity, table.num_rows)
