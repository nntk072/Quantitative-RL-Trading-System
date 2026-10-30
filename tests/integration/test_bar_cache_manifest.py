from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from market_data.cache.bars import (
    BAR_CACHE_MANIFEST_SCHEMA_VERSION,
    BAR_CACHE_TRANSFORM_ID,
    bar_cache_is_complete,
    load_bar_cache,
    write_bar_cache,
)


def test_bar_cache_write_failure_preserves_completed_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "bars.parquet"
    index = pd.date_range("2025-01-06 16:30", periods=2, freq="min", tz="Etc/GMT-3")
    original = pd.DataFrame({"close": [100.0, 101.0]}, index=index)
    identity = {
        "schema_version": BAR_CACHE_MANIFEST_SCHEMA_VERSION,
        "transform": BAR_CACHE_TRANSFORM_ID,
        "cache_id": "cache:original",
        "inputs": {},
    }
    write_bar_cache(cache_path, original, identity)
    assert bar_cache_is_complete(cache_path)
    original_bytes = cache_path.read_bytes()
    manifest_path = Path(f"{cache_path}.manifest.json")
    original_manifest = manifest_path.read_bytes()

    def fail_parquet_write(self: pd.DataFrame, path: str | Path, **kwargs: object) -> None:
        raise OSError("simulated interrupted parquet write")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", fail_parquet_write)
    with pytest.raises(OSError, match="simulated interrupted"):
        write_bar_cache(cache_path, original.assign(close=[0.0, 0.0]), {"cache_id": "new"})

    assert cache_path.read_bytes() == original_bytes
    assert manifest_path.read_bytes() == original_manifest
    assert bar_cache_is_complete(cache_path)
    loaded = load_bar_cache(cache_path, identity)
    assert loaded is not None
    pd.testing.assert_frame_equal(loaded, original, check_freq=False)


def test_failed_manifest_publish_cannot_reuse_replaced_parquet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "bars.parquet"
    index = pd.date_range("2025-01-06 16:30", periods=2, freq="min", tz="Etc/GMT-3")
    original = pd.DataFrame({"close": [100.0, 101.0]}, index=index)
    identity = {
        "schema_version": BAR_CACHE_MANIFEST_SCHEMA_VERSION,
        "transform": BAR_CACHE_TRANSFORM_ID,
        "cache_id": "cache:manifest-failure",
        "inputs": {},
    }
    write_bar_cache(cache_path, original, identity)
    assert bar_cache_is_complete(cache_path)

    def fail_manifest_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated interrupted manifest publish")

    monkeypatch.setattr("market_data.cache.storage.write_json_atomic", fail_manifest_write)
    with pytest.raises(OSError, match="interrupted manifest"):
        write_bar_cache(cache_path, original.assign(close=[90.0, 91.0]), identity)

    assert not bar_cache_is_complete(cache_path)
    assert load_bar_cache(cache_path, identity) is None


def test_bar_cache_loader_rejects_a_different_semantic_identity(tmp_path: Path) -> None:
    cache_path = tmp_path / "bars.parquet"
    index = pd.date_range("2025-01-06 16:30", periods=1, freq="min", tz="Etc/GMT-3")
    frame = pd.DataFrame({"close": [100.0]}, index=index)
    identity = {
        "schema_version": 1,
        "transform": "test-transform",
        "cache_id": "timezone-a",
        "inputs": {},
    }
    write_bar_cache(cache_path, frame, identity)

    assert load_bar_cache(cache_path, identity | {"cache_id": "timezone-b"}) is None


def test_bar_cache_without_completion_manifest_is_incomplete(tmp_path: Path) -> None:
    cache_path = tmp_path / "bars.parquet"
    cache_path.write_bytes(b"old sidecar-only cache")

    assert not bar_cache_is_complete(cache_path)


def test_bar_cache_loader_treats_corrupt_parquet_as_a_cache_miss(tmp_path: Path) -> None:
    cache_path = tmp_path / "bars.parquet"
    index = pd.date_range("2025-01-06 16:30", periods=1, freq="min", tz="Etc/GMT-3")
    frame = pd.DataFrame({"close": [100.0]}, index=index)
    identity = {
        "schema_version": 1,
        "transform": "test-transform",
        "cache_id": "cache:corrupt-test",
        "inputs": {},
    }
    write_bar_cache(cache_path, frame, identity)
    cache_path.write_bytes(b"corrupt parquet payload")

    assert load_bar_cache(cache_path, identity) is None


def test_bar_cache_writer_rejects_empty_frames(tmp_path: Path) -> None:
    cache_path = tmp_path / "bars.parquet"
    empty = pd.DataFrame({"close": pd.Series(dtype="float64")})

    with pytest.raises(ValueError, match="empty bar cache"):
        write_bar_cache(cache_path, empty, {})

    assert not cache_path.exists()
