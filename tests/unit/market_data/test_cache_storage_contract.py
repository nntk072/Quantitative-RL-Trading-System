from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from market_data.cache.storage import (
    cache_is_complete,
    cache_metadata_path,
    load_parquet_cache,
    mark_cache_complete,
    parquet_cache_is_complete,
    write_parquet_cache,
)


@pytest.fixture
def pickle_backed_parquet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep cache identity/atomicity tests independent of an installed parquet engine."""

    def write_frame(frame: pd.DataFrame, path: str | Path, *, index: bool = True) -> None:
        frame.to_pickle(path)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", write_frame)
    monkeypatch.setattr(pd, "read_parquet", lambda path: pd.read_pickle(path))


def test_directory_completion_marker_is_written_atomically(tmp_path: Path) -> None:
    entry = tmp_path / "cache-entry"

    assert mark_cache_complete(entry, {"identity": "fixture"}) == entry

    assert cache_is_complete(entry)
    assert cache_metadata_path(entry).read_text(encoding="utf-8").find("fixture") >= 0


def test_parquet_cache_load_requires_matching_identity_and_ordering(
    tmp_path: Path, pickle_backed_parquet: None
) -> None:
    path = tmp_path / "nested" / "bars.parquet"
    identity = {"cache_id": "fixture-v1", "feature_version": "v3"}
    frame = pd.DataFrame({"timestamp": [10, 20, 30], "close": [1.0, 2.0, 3.0]})
    write_parquet_cache(path, frame, identity, index=False, ordered_column="timestamp")

    assert parquet_cache_is_complete(path)
    cached = load_parquet_cache(path, identity, ordered_column="timestamp", unique_order=True)
    assert cached is not None
    pd.testing.assert_frame_equal(cached, frame)
    assert load_parquet_cache(path, {"cache_id": "other"}, ordered_column="timestamp") is None


def test_parquet_cache_load_rejects_nonmonotonic_or_nonunique_order(
    tmp_path: Path, pickle_backed_parquet: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "bars.parquet"
    identity = {"cache_id": "ordered"}
    frame = pd.DataFrame({"timestamp": [10, 20, 10], "close": [1.0, 2.0, 3.0]})
    write_parquet_cache(path, frame, identity, index=False, ordered_column="timestamp")

    assert load_parquet_cache(path, identity, ordered_column="timestamp") is None
    # The manifest still describes an increasing sequence; enforce uniqueness separately.
    duplicate = pd.DataFrame({"timestamp": [10, 10], "close": [1.0, 2.0]})
    write_parquet_cache(path, duplicate, identity, index=False, ordered_column="timestamp")
    assert load_parquet_cache(path, identity, ordered_column="timestamp") is not None
    assert load_parquet_cache(path, identity, ordered_column="timestamp", unique_order=True) is None

    def fail_read(_path: str | Path) -> pd.DataFrame:
        raise OSError("bad cache payload")

    monkeypatch.setattr(pd, "read_parquet", fail_read)
    assert load_parquet_cache(path, identity, ordered_column="timestamp") is None


def test_parquet_cache_writer_requires_declared_order_column(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing ordering column"):
        write_parquet_cache(
            tmp_path / "bars.parquet",
            pd.DataFrame({"close": [1.0]}),
            {"cache_id": "missing-order"},
            ordered_column="timestamp",
        )


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"identity": "not-a-mapping"},
        {
            "identity": {"cache_id": "fixture"},
            "row_count": 1,
            "parquet_size_bytes": 1,
            "parquet_mtime_ns": 1,
            "parquet_inode": 1,
        },
    ],
)
def test_parquet_cache_reader_rejects_malformed_manifest_payloads(
    tmp_path: Path, pickle_backed_parquet: None, payload: object
) -> None:
    path = tmp_path / "bars.parquet"
    write_parquet_cache(
        path,
        pd.DataFrame({"timestamp": [10], "close": [1.0]}),
        {"cache_id": "fixture"},
        index=False,
        ordered_column="timestamp",
    )
    Path(f"{path}.manifest.json").write_text(json.dumps(payload), encoding="utf-8")

    assert not parquet_cache_is_complete(path)
    assert load_parquet_cache(path, {"cache_id": "fixture"}, ordered_column="timestamp") is None


@pytest.mark.parametrize(
    "replacement",
    [
        pd.DataFrame({"timestamp": [10, 20], "close": [1.0, 2.0]}),
        pd.DataFrame({"timestamp": [9, 20, 30], "close": [0.0, 2.0, 3.0]}),
        pd.DataFrame({"timestamp": [10, 20, 31], "close": [1.0, 2.0, 4.0]}),
    ],
)
def test_parquet_cache_reader_rejects_changed_row_count_or_ordered_endpoints(
    tmp_path: Path,
    pickle_backed_parquet: None,
    monkeypatch: pytest.MonkeyPatch,
    replacement: pd.DataFrame,
) -> None:
    path = tmp_path / "bars.parquet"
    identity = {"cache_id": "fixture"}
    frame = pd.DataFrame({"timestamp": [10, 20, 30], "close": [1.0, 2.0, 3.0]})
    write_parquet_cache(path, frame, identity, index=False, ordered_column="timestamp")
    monkeypatch.setattr(pd, "read_parquet", lambda _path: replacement)

    assert load_parquet_cache(path, identity, ordered_column="timestamp") is None


def test_parquet_cache_is_invalidated_when_payload_age_changes(
    tmp_path: Path, pickle_backed_parquet: None
) -> None:
    path = tmp_path / "bars.parquet"
    identity = {"cache_id": "freshness"}
    write_parquet_cache(
        path,
        pd.DataFrame({"timestamp": [10, 20], "close": [1.0, 2.0]}),
        identity,
        index=False,
        ordered_column="timestamp",
    )
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

    assert not parquet_cache_is_complete(path)
    assert load_parquet_cache(path, identity, ordered_column="timestamp") is None
