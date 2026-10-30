"""Semantic identity and storage for executable tick-book caches."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from market_data.cache.identity import market_data_cache_id
from market_data.cache.storage import (
    load_parquet_cache,
    parquet_cache_is_complete,
    parquet_cache_manifest_path,
    write_parquet_cache,
)

TICK_CACHE_MANIFEST_SCHEMA_VERSION = 1
TICK_CACHE_TRANSFORM_ID = "mt5-tick-csv-to-book-v1"


def tick_cache_manifest_path(cache_path: str | Path) -> Path:
    """Return the completion manifest path associated with a tick parquet."""
    return parquet_cache_manifest_path(cache_path)


def build_tick_cache_identity(
    *,
    source_path: str | Path,
    source_sha256: str,
    timezone: str,
    session_start: str | None,
    session_end: str | None,
    price_grid_identity: str,
    cache_version: str,
) -> dict[str, Any]:
    """Identify source bytes and every setting that changes a TickBook."""
    resolved_source_path = str(Path(source_path).resolve())
    inputs = {
        "source_path": resolved_source_path,
        "source_sha256": source_sha256,
        "timezone": timezone,
        "session_start": session_start,
        "session_end": session_end,
        "price_grid_identity": price_grid_identity,
        "cache_version": cache_version,
    }
    return {
        "schema_version": TICK_CACHE_MANIFEST_SCHEMA_VERSION,
        "transform": TICK_CACHE_TRANSFORM_ID,
        "cache_id": market_data_cache_id(
            dataset_id=resolved_source_path,
            transform=TICK_CACHE_TRANSFORM_ID,
            config=inputs,
            schema_version=TICK_CACHE_MANIFEST_SCHEMA_VERSION,
        ),
        "inputs": inputs,
    }


def tick_cache_is_complete(cache_path: str | Path) -> bool:
    """Check that a tick parquet has its semantic completion manifest."""
    if not parquet_cache_is_complete(cache_path):
        return False
    manifest = json.loads(tick_cache_manifest_path(cache_path).read_text(encoding="utf-8"))
    return bool(
        manifest["identity"].get("schema_version") == TICK_CACHE_MANIFEST_SCHEMA_VERSION
        and manifest["identity"].get("transform") == TICK_CACHE_TRANSFORM_ID
    )


def load_tick_cache(
    cache_path: str | Path, expected_identity: dict[str, Any]
) -> pd.DataFrame | None:
    """Load a tick cache only when its semantic identity and timestamp order match."""
    return load_parquet_cache(
        cache_path,
        expected_identity,
        ordered_column="ts_ns",
    )


def write_tick_cache(
    cache_path: str | Path,
    frame: pd.DataFrame,
    identity: dict[str, Any],
) -> Path:
    """Atomically publish tick arrays and their semantic completion manifest."""
    required_columns = {"ts_ns", "bid", "ask"}
    missing = required_columns.difference(frame.columns)
    if missing:
        raise ValueError(f"tick cache frame is missing columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("cannot publish an empty tick cache")
    return write_parquet_cache(
        cache_path,
        frame,
        identity,
        index=False,
        ordered_column="ts_ns",
    )
