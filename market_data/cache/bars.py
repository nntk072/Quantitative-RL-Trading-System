"""Identity and atomic storage for cleaned, session-labeled bar caches."""

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

BAR_CACHE_MANIFEST_SCHEMA_VERSION = 1
BAR_CACHE_TRANSFORM_ID = "bar-cleaning-session-labels-v1"


def bar_cache_path(cache_dir: str | Path, symbol: str, timeframe: str, cache_version: str) -> Path:
    """Build the canonical bar-cache path from its semantic cache version."""
    return Path(cache_dir) / f"{symbol}_{timeframe}_{cache_version}.parquet"


def bar_cache_manifest_path(cache_path: str | Path) -> Path:
    """Return the completion manifest path associated with a bar parquet."""
    return parquet_cache_manifest_path(cache_path)


def bar_cache_is_complete(cache_path: str | Path) -> bool:
    """Check for a non-empty parquet and structurally valid completion manifest."""
    if not parquet_cache_is_complete(cache_path):
        return False
    manifest = json.loads(bar_cache_manifest_path(cache_path).read_text(encoding="utf-8"))
    return bool(
        manifest["identity"].get("schema_version") == BAR_CACHE_MANIFEST_SCHEMA_VERSION
        and manifest["identity"].get("transform") == BAR_CACHE_TRANSFORM_ID
        and manifest["row_count"] > 0
    )


def build_bar_cache_identity(
    *,
    dataset_id: str,
    symbol: str,
    timeframe: str,
    source_identity: str,
    timezone: str,
    ny_session_end: str,
    timestamp_convention: str,
    price_grid_identity: str | None,
) -> dict[str, Any]:
    """Describe every source and configuration input that changes cached bars."""
    transform_config = {
        "dataset_id": dataset_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "source_identity": source_identity,
        "timezone": timezone,
        "ny_session_end": ny_session_end,
        "timestamp_convention": timestamp_convention,
        "price_grid_identity": price_grid_identity,
    }
    return {
        "schema_version": BAR_CACHE_MANIFEST_SCHEMA_VERSION,
        "transform": BAR_CACHE_TRANSFORM_ID,
        "cache_id": market_data_cache_id(
            dataset_id=f"{dataset_id}:{symbol}:{timeframe}:{source_identity}",
            transform=BAR_CACHE_TRANSFORM_ID,
            config=transform_config,
            schema_version=BAR_CACHE_MANIFEST_SCHEMA_VERSION,
        ),
        "inputs": transform_config,
    }


def load_bar_cache(
    cache_path: str | Path, expected_identity: dict[str, Any]
) -> pd.DataFrame | None:
    """Load a complete cache only when its semantic identity and shape match."""
    return load_parquet_cache(cache_path, expected_identity, unique_order=True)


def write_bar_cache(
    cache_path: str | Path,
    frame: pd.DataFrame,
    identity: dict[str, Any],
) -> Path:
    """Atomically publish a parquet cache, then its completion manifest."""
    if frame.empty:
        raise ValueError("cannot publish an empty bar cache")
    return write_parquet_cache(cache_path, frame, identity)
