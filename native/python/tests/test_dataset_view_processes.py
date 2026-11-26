"""Spawn and fork safety of DatasetView cache containers across processes (SHARED-DATA-ABI).

Two worker processes at most, per start method. Each worker reads the same cache file, decodes it
with the native module and reports its content hash. Corrupt files must be refused in the worker
too. Results come back as plain strings, so no exception object crosses the process boundary.
"""

from __future__ import annotations

import multiprocessing
from pathlib import Path
from typing import Any

import pytest

from market_data.native_abi import read_cache, write_cache_atomic

WORKERS = 2


def _load(path: str) -> str:
    """Worker: decode the cache at ``path`` and return its hash, or a refusal description."""
    import importlib

    native: Any = importlib.import_module("qrl_native")
    try:
        view = native.dataset_view_from_cache_bytes(read_cache(Path(path)))
    except native.AbiError as error:
        return f"refused:{type(error).__name__}:{error}"
    return f"ok:{view.content_hash}"


@pytest.mark.parametrize("method", ["spawn", "fork"])
def test_two_workers_decode_the_same_cache_to_the_same_hash(
    tmp_path: Path, native: Any, small_view_bytes: bytes, method: str
) -> None:
    path = tmp_path / "view.qrlds"
    write_cache_atomic(path, small_view_bytes)
    expected = native.dataset_view_from_cache_bytes(small_view_bytes).content_hash
    context = multiprocessing.get_context(method)
    with context.Pool(processes=WORKERS) as pool:
        results = pool.map(_load, [str(path)] * WORKERS)
    assert results == [f"ok:{expected}"] * WORKERS


@pytest.mark.parametrize("method", ["spawn", "fork"])
def test_workers_refuse_a_corrupt_cache_file(
    tmp_path: Path, small_view_bytes: bytes, method: str
) -> None:
    path = tmp_path / "view.qrlds"
    data = bytearray(small_view_bytes)
    data[len(data) // 2] ^= 0x10
    write_cache_atomic(path, bytes(data))
    context = multiprocessing.get_context(method)
    with context.Pool(processes=WORKERS) as pool:
        results = pool.map(_load, [str(path)] * WORKERS)
    assert all(result.startswith("refused:AbiCacheError:") for result in results), results
