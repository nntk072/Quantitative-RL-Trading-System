from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from artifacts.atomic import write_json_atomic


def cache_metadata_path(entry: str | Path) -> Path:
    return Path(entry) / "manifest.json"


def mark_cache_complete(entry: str | Path, metadata: dict[str, object]) -> Path:
    root = Path(entry)
    root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(cache_metadata_path(root), metadata)
    return root


def cache_is_complete(entry: str | Path) -> bool:
    return cache_metadata_path(entry).is_file()


def parquet_cache_manifest_path(cache_path: str | Path) -> Path:
    """Return the completion manifest path for a parquet cache file."""
    return Path(f"{cache_path}.manifest.json")


def _read_parquet_cache_manifest(cache_path: Path) -> dict[str, Any] | None:
    manifest_path = parquet_cache_manifest_path(cache_path)
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict):
        return None
    identity = manifest.get("identity")
    row_count = manifest.get("row_count")
    parquet_size = manifest.get("parquet_size_bytes")
    parquet_mtime = manifest.get("parquet_mtime_ns")
    parquet_inode = manifest.get("parquet_inode")
    if (
        not isinstance(identity, dict)
        or not isinstance(identity.get("cache_id"), str)
        or not isinstance(row_count, int)
        or row_count < 0
        or not isinstance(parquet_size, int)
        or parquet_size <= 0
        or not isinstance(parquet_mtime, int)
        or parquet_mtime <= 0
        or not isinstance(parquet_inode, int)
        or parquet_inode <= 0
    ):
        return None
    if row_count and not all(
        isinstance(manifest.get(key), str) for key in ("first_value", "last_value")
    ):
        return None
    return manifest


def parquet_cache_is_complete(cache_path: str | Path) -> bool:
    """Check for a non-empty parquet plus a structurally valid completion manifest."""
    path = Path(cache_path)
    manifest = _read_parquet_cache_manifest(path)
    if manifest is None or not path.is_file() or path.stat().st_size == 0:
        return False
    stat = path.stat()
    return (
        manifest.get("row_count", 0) > 0
        and manifest.get("parquet_size_bytes") == stat.st_size
        and manifest.get("parquet_mtime_ns") == stat.st_mtime_ns
        and manifest.get("parquet_inode") == stat.st_ino
    )


def load_parquet_cache(
    cache_path: str | Path,
    expected_identity: dict[str, Any],
    *,
    ordered_column: str | None = None,
    unique_order: bool = False,
) -> pd.DataFrame | None:
    """Load a parquet cache only when identity and recorded ordering still match."""
    path = Path(cache_path)
    if not path.is_file():
        return None
    manifest = _read_parquet_cache_manifest(path)
    if (
        manifest is None
        or manifest.get("identity") != expected_identity
        or not parquet_cache_is_complete(path)
    ):
        return None
    try:
        frame = pd.read_parquet(path)
    except (OSError, ValueError):
        return None
    if len(frame) != manifest["row_count"]:
        return None
    ordered_values = frame[ordered_column] if ordered_column is not None else frame.index
    if len(frame):
        first_value = (
            ordered_values.iloc[0] if isinstance(ordered_values, pd.Series) else ordered_values[0]
        )
        last_value = (
            ordered_values.iloc[-1] if isinstance(ordered_values, pd.Series) else ordered_values[-1]
        )
        if str(first_value) != manifest.get("first_value"):
            return None
        if str(last_value) != manifest.get("last_value"):
            return None
    if not ordered_values.is_monotonic_increasing:
        return None
    if unique_order and not ordered_values.is_unique:
        return None
    return frame


def write_parquet_cache(
    cache_path: str | Path,
    frame: pd.DataFrame,
    identity: dict[str, Any],
    *,
    index: bool = True,
    ordered_column: str | None = None,
) -> Path:
    """Atomically publish a parquet file and its semantic completion manifest."""
    path = Path(cache_path)
    if ordered_column is not None and ordered_column not in frame.columns:
        raise ValueError(f"cache frame is missing ordering column {ordered_column!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=path.suffix, dir=path.parent
    )
    os.close(fd)
    temporary_path = Path(temporary_name)
    try:
        frame.to_parquet(temporary_path, index=index)
        os.replace(temporary_path, path)
        stat = path.stat()
        ordered_values = frame[ordered_column] if ordered_column is not None else frame.index
        first_value = (
            ordered_values.iloc[0]
            if isinstance(ordered_values, pd.Series) and len(frame)
            else (ordered_values[0] if len(frame) else None)
        )
        last_value = (
            ordered_values.iloc[-1]
            if isinstance(ordered_values, pd.Series) and len(frame)
            else (ordered_values[-1] if len(frame) else None)
        )
        manifest = {
            "identity": identity,
            "row_count": len(frame),
            "first_value": str(first_value) if first_value is not None else None,
            "last_value": str(last_value) if last_value is not None else None,
            "parquet_size_bytes": stat.st_size,
            "parquet_mtime_ns": stat.st_mtime_ns,
            "parquet_inode": stat.st_ino,
        }
        write_json_atomic(parquet_cache_manifest_path(path), manifest, default=None)
    finally:
        temporary_path.unlink(missing_ok=True)
    return path
