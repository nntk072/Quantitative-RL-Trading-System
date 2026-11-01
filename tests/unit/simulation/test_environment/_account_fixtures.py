"""Synthetic bars and features shared by TradingEnv observation tests."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _make_bars(n: int = 200, seed: int = 7) -> pd.DataFrame:
    """Build deterministic market bars for TradingEnv tests."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-06 16:30", periods=n, freq="1min", tz="Etc/GMT-3")
    close = 20000.0 + np.cumsum(rng.normal(0, 2, n))
    return pd.DataFrame(
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


def _make_features(bars: pd.DataFrame, seed: int = 7) -> pd.DataFrame:
    """Build deterministic feature rows aligned to a synthetic bar index."""
    rng = np.random.default_rng(seed)
    n = len(bars)
    return pd.DataFrame(
        {
            "london_high": 20500.0,
            "london_low": 19500.0,
            "asian_high": 20300.0,
            "asian_low": 19700.0,
            "volume_spike": rng.uniform(0.5, 2.5, n),
            "last_swing_high": np.nan,
            "last_swing_low": np.nan,
        },
        index=bars.index,
    )
