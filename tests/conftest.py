"""Assign execution markers consistently for the test collection."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from gymnasium import spaces

EXECUTION_MARKERS = frozenset({"unit", "integration", "slow", "gpu", "triton", "research"})


@pytest.fixture
def m1_bars() -> pd.DataFrame:
    """Small synthetic M1 bar DataFrame (500 bars, NY session, UTC+3)."""
    n = 500
    idx = pd.date_range("2025-01-06 01:05", periods=n, freq="1min", tz="Etc/GMT-3")
    rng = np.random.default_rng(42)
    close = 20000.0 + np.cumsum(rng.normal(0, 2, n))
    bars = pd.DataFrame(
        {
            "open": close - rng.uniform(0, 1, n),
            "high": close + rng.uniform(0, 2, n),
            "low": close - rng.uniform(0, 2, n),
            "close": close,
            "tickvol": rng.integers(10, 200, n),
            "volume": rng.integers(1000, 5000, n),
            "vol": np.zeros(n, dtype=int),
            "spread": np.full(n, 0.6),
            "gap_flag": False,
            "session_id": 0,
        },
        index=idx,
    )
    bars.index.name = "datetime"
    return bars


@pytest.fixture
def dict_obs_space() -> spaces.Dict:
    """Gymnasium Dict observation space matching TradingEnv (T=10, F=8, A=5)."""
    return spaces.Dict(
        {
            "seq": spaces.Box(low=-10.0, high=10.0, shape=(10, 8), dtype=np.float32),
            "account": spaces.Box(low=-1.0, high=1.0, shape=(6,), dtype=np.float32),
        }
    )


def execution_markers_for_test(
    path: Path, existing_markers: frozenset[str] = frozenset()
) -> tuple[str, ...]:
    """Return explicit path and default execution categories for one test."""
    parts = path.parts
    markers: list[str] = []
    if "integration" in parts or "test_integration" in parts or "test_backtest" in parts:
        markers.append("integration")
    elif "test_research" in parts or "test_bench" in parts:
        markers.append("research")
    if not (existing_markers | set(markers)).intersection(EXECUTION_MARKERS):
        markers.append("unit")
    return tuple(markers)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Classify unmarked tests as unit and add path-level execution categories."""
    for item in items:
        existing = {mark.name for mark in item.iter_markers()}
        for marker_name in execution_markers_for_test(Path(str(item.path)), frozenset(existing)):
            if marker_name not in existing:
                item.add_marker(getattr(pytest.mark, marker_name))
                existing.add(marker_name)
        if not existing.intersection(EXECUTION_MARKERS):
            item.add_marker(pytest.mark.unit)
