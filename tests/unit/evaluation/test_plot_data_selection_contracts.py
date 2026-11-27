"""Data-selection contracts for exploratory and defense plotting helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from evaluation.plotting.data_plots import (
    _select_hist_columns,
    _signal_columns,
    _slice_calendar_day,
)
from evaluation.plotting.defense_plots import _flag_union, _mean_path


def test_histograms_prioritize_curated_features_then_fall_back_to_available_data() -> None:
    numeric = pd.DataFrame(
        {
            "unlisted": [1.0, 2.0],
            "atr": [3.0, 4.0],
            "entry_long": [0.0, 1.0],
            "macd": [float("nan"), float("nan")],
        }
    )

    assert _select_hist_columns(numeric, 2) == ["atr", "entry_long"]
    assert _select_hist_columns(numeric[["unlisted"]], 1) == ["unlisted"]
    assert _select_hist_columns(numeric[["macd"]], 2) == []


def test_signal_selection_includes_exact_and_timeframe_prefixed_columns_once() -> None:
    features = pd.DataFrame(
        columns=["entry_long", "M5_entry_long", "H1_entry_long", "M5_price_in_ifvg_bull"]
    )

    assert _signal_columns(features, ("entry_long",)) == [
        "entry_long",
        "M5_entry_long",
        "H1_entry_long",
    ]


def test_calendar_day_slice_keeps_off_session_bars_and_prior_geometry_context() -> None:
    index = pd.date_range("2025-01-01 23:00", periods=1500, freq="min", tz="Etc/GMT-3")
    bars = pd.DataFrame({"close": np.arange(len(index), dtype=float)}, index=index)

    plot_bars, lookback = _slice_calendar_day(
        bars,
        pd.Timestamp("2025-01-02"),
        lookback_bars=10,
    )

    assert len(plot_bars) == 1440
    assert plot_bars.index[0] == pd.Timestamp("2025-01-02 00:00", tz="Etc/GMT-3")
    assert lookback.index[0] == index[50]
    assert lookback.index[-1] == plot_bars.index[-1]


def test_defense_flag_union_uses_any_available_timeframe_and_defaults_missing_flags_false() -> None:
    index = pd.date_range("2025-01-02", periods=4, freq="min")
    features = pd.DataFrame(
        {
            "M5_price_in_ifvg_bull": [0.0, 1.0, np.nan, 0.0],
            "H1_price_in_ifvg_bear": [0.0, 0.0, 1.0, 0.0],
        },
        index=index,
    )

    assert _flag_union(features, ("price_in_ifvg_bull", "price_in_ifvg_bear")).tolist() == [
        False,
        True,
        True,
        False,
    ]
    assert not _flag_union(features, ("missing_flag",)).any()


def test_defense_mean_path_purges_nearby_onsets_and_skips_incomplete_horizons() -> None:
    close = np.asarray([100.0, 110.0, 121.0, 100.0, 105.0, 110.0])
    onset = np.asarray([True, True, True, False, False, True])

    path = _mean_path(close, onset, horizon=1, purge=1)

    # Onset 1 is purged next to onset 0; onset 5 has no complete future horizon.
    assert path[0] == 0.0
    assert path[1] == pytest.approx((0.10 + (100.0 / 121.0 - 1.0)) / 2.0)
