"""Tests for CFD tick-count activity (ignore all-zero vol)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from features.technical.indicators import vwap_level
from market_data.transforms.activity import (
    activity_series,
    attach_activity,
    tick_counts_from_index,
)


def test_activity_ignores_zero_volume_uses_tickvol() -> None:
    idx = pd.date_range("2025-01-02", periods=4, freq="1min")
    df = pd.DataFrame(
        {"volume": np.zeros(4), "vol": np.zeros(4), "tickvol": [10.0, 20.0, 30.0, 40.0]},
        index=idx,
    )
    act = activity_series(df)
    assert act is not None
    assert list(act.to_numpy()) == [10.0, 20.0, 30.0, 40.0]


def test_activity_none_when_only_zero_vol() -> None:
    idx = pd.date_range("2025-01-02", periods=3, freq="1min")
    df = pd.DataFrame({"vol": [0, 0, 0]}, index=idx)
    assert activity_series(df) is None


def test_tick_counts_from_index() -> None:
    bars = pd.date_range("2025-01-02 16:30", periods=3, freq="1min", tz="Etc/GMT-3")
    ticks = pd.DatetimeIndex(
        [
            bars[0] + pd.Timedelta(seconds=1),
            bars[0] + pd.Timedelta(seconds=2),
            bars[1] + pd.Timedelta(seconds=1),
        ]
    )
    counts = tick_counts_from_index(pd.DatetimeIndex(bars), ticks)
    assert list(counts.to_numpy()) == [2.0, 1.0, 0.0]


def test_vwap_uses_tickvol_not_zero_volume() -> None:
    idx = pd.date_range("2025-01-02 16:30", periods=3, freq="1min", tz="Etc/GMT-3")
    close = np.array([100.0, 102.0, 104.0])
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": np.zeros(3),
            "tickvol": np.array([1.0, 1.0, 1.0]),
            "session_id": np.zeros(3, dtype=int),
        },
        index=idx,
    )
    vwap = vwap_level(df)
    typical = (df["high"] + df["low"] + df["close"]) / 3
    assert vwap.iloc[0] == typical.iloc[0]
    assert vwap.notna().all()


def test_activity_prefers_tick_count_and_does_not_mutate_input() -> None:
    source = pd.DataFrame({"tick_count": [3, 4], "tickvol": [30, 40]})

    result = attach_activity(source)

    assert result["activity"].tolist() == [3.0, 4.0]
    assert "activity" not in source.columns


def test_activity_falls_back_from_dead_tickvol_to_live_volume() -> None:
    source = pd.DataFrame({"tickvol": [0, 0, 0], "volume": [5, 6, 7]})

    actual = activity_series(source)

    assert actual is not None
    assert actual.tolist() == [5.0, 6.0, 7.0]


def test_tick_counts_for_empty_bar_index_returns_named_empty_series() -> None:
    result = tick_counts_from_index(pd.DatetimeIndex([]), pd.DatetimeIndex([]))

    assert result.empty
    assert result.name == "tick_count"
