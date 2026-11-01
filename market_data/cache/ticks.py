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
    """Return the completion manifest path associated with a tick parquet.

    Args:
        cache_path: Path or filename identifying the cache.

    Returns:
        Path returned by ``tick_cache_manifest_path``.
    """
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
    """Identify source bytes and every setting that changes a TickBook.

    Args:
        source_path: Path or filename identifying the source.
        source_sha256: Text or path value identifying the source sha256.
        timezone: Text or path value identifying the timezone.
        session_start: Session start used by the operation described above.
        session_end: Session end used by the operation described above.
        price_grid_identity: Text or path value identifying the price grid identity.
        cache_version: Text or path value identifying the cache version.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
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
    """Check that a tick parquet has its semantic completion manifest.

    Args:
        cache_path: Path or filename identifying the cache.

    Returns:
        Whether tick cache is complete meets the requested condition.
    """
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
    """Load a tick cache only when its semantic identity and timestamp order match.

    Args:
        cache_path: Path or filename identifying the cache.
        expected_identity: Key-value data used for the expected identity.

    Returns:
        DataFrame returned by ``load_tick_cache``.
    """
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
    """Atomically publish tick arrays and their semantic completion manifest.

    Args:
        cache_path: Path or filename identifying the cache.
        frame: Input data frame to process.
        identity: Key-value data used for the identity.

    Returns:
        Path returned by ``write_tick_cache``.
    """
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
