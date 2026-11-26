"""Fixtures for DatasetView tests: small valid bars and feature blocks built from NumPy arrays."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pytest

T0 = 1_700_000_000_000_000_000
MINUTE = 60_000_000_000

ViewFactory = Callable[..., Any]


def _bar_batch(native: Any, rows: int = 6) -> Any:
    event = T0 + np.arange(rows, dtype=np.int64) * MINUTE
    return native.BarBatch.from_columns(
        schema_id="market-event.v1",
        instrument_id="US100",
        source_id="mt5-export",
        columns={
            "event_time_ns": event,
            "close_time_ns": event + MINUTE,
            "available_at_ns": event + MINUTE,
            "source_sequence": np.arange(rows, dtype=np.int64),
            "open": np.full(rows, 100.0),
            "high": np.full(rows, 101.0),
            "low": np.full(rows, 99.0),
            "close": np.full(rows, 100.5),
            "volume": np.full(rows, 10.0),
            "volume_valid": np.ones(rows, dtype=np.uint8),
        },
    )


def _feature_block(native: Any, rows: int = 6, width: int = 2) -> Any:
    event = T0 + np.arange(rows, dtype=np.int64) * MINUTE
    values = np.full((rows, width), 0.25)
    valid = np.ones((rows, width), dtype=np.uint8)
    values[0] = np.nan  # warm-up row is missing
    valid[0] = 0
    return native.FeatureRowBlock.from_columns(
        schema_id="feature-row.v1",
        instrument_id="US100",
        feature_set_id="core-v1",
        feature_version="1.0.0",
        content_hash="sha256:abc",
        width=width,
        columns={
            "event_time_ns": event,
            "available_at_ns": event,
            "session_eligible": np.ones(rows, dtype=np.uint8),
            "values": np.ascontiguousarray(values),
            "values_valid": np.ascontiguousarray(valid),
        },
    )


@pytest.fixture
def native() -> Any:
    """The built ``qrl_native`` extension; the test is skipped when it is not importable."""
    return pytest.importorskip("qrl_native")


@pytest.fixture
def make_view(native: Any) -> ViewFactory:
    """Factory returning a DatasetView over six aligned rows with the given folds and fitted state."""

    def build(folds: list[tuple[int, ...]], fitted: tuple[str, int, int] | None = None) -> Any:
        return native.DatasetView(
            _bar_batch(native, 6), _feature_block(native, 6, 2), folds, fitted
        )

    return build


@pytest.fixture
def small_view_bytes(native: Any) -> bytes:
    """Cache container bytes of a four-row view, small enough to corrupt every byte."""
    view = native.DatasetView(
        _bar_batch(native, 4),
        _feature_block(native, 4, 2),
        [(0, 2, 3, 4, 0, 0)],
        ("norm-v1", 0, 2),
    )
    return bytes(view.to_cache_bytes())
