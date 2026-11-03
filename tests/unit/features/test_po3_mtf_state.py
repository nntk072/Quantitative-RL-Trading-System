"""Causal PO3 state composition on an MTF source timeframe."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from features.context.entry_ideas import build_entry_idea_features
from features.pipeline.po3_stage import _build_po3_timeframe_state
from market_data.transforms.align import align_timeframes, timeframe_close_times


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    index = pd.date_range("2025-01-06 16:30", periods=5, freq="5min", tz="UTC")
    bars = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 100.0, 100.0],
            "high": [101.0, 103.0, 101.5, 102.0, 102.0],
            "low": [98.0, 99.0, 99.5, 99.5, 99.5],
            "close": [100.0, 102.0, 101.0, 101.0, 101.0],
        },
        index=index,
    )
    sweeps = pd.DataFrame(
        {
            "sweep_low": [1.0, 0.0, 0.0, 0.0, 0.0],
            "sweep_high": np.zeros(5),
            "sweep_low_level": [99.0, np.nan, np.nan, np.nan, np.nan],
            "sweep_high_level": np.full(5, np.nan),
        },
        index=index,
    )
    zones = pd.DataFrame(
        {
            "ifvg_bull_confirmed": [0.0, 0.0, 0.0, 1.0, 0.0],
            "ifvg_bear_confirmed": [0.0, 0.0, 1.0, 0.0, 0.0],
            "ifvg_bull_fvg_origin_bar": [np.nan, np.nan, np.nan, 3.0, 3.0],
            "ifvg_bear_fvg_origin_bar": [np.nan, np.nan, 2.0, 2.0, 2.0],
            "ifvg_bull_low": [np.nan, np.nan, np.nan, 99.5, 99.5],
            "ifvg_bull_high": [np.nan, np.nan, np.nan, 100.5, 100.5],
            "ifvg_bear_low": [np.nan, np.nan, 99.5, 99.5, 99.5],
            "ifvg_bear_high": [np.nan, np.nan, 100.5, 100.5, 100.5],
            "ifvg_bull_active": [0.0, 0.0, 0.0, 1.0, 1.0],
            "ifvg_bear_active": [0.0, 0.0, 1.0, 1.0, 1.0],
        },
        index=index,
    )
    return bars, sweeps, zones


def _aligned_candidate(
    source_bars: pd.DataFrame,
    source_sweeps: pd.DataFrame,
    source_zones: pd.DataFrame,
    primary_bars: pd.DataFrame,
    phase_mode: str,
) -> pd.DataFrame:
    state = _build_po3_timeframe_state(
        source_bars,
        source_sweeps,
        pd.DataFrame(index=source_bars.index),
        source_zones,
        phase_mode=phase_mode,
        max_ifvg_age_bars=50,
    )
    source_block = pd.concat(
        [state, source_zones[["ifvg_bull_active", "ifvg_bear_active"]]], axis=1
    )
    aligned = align_timeframes(
        primary_bars,
        {"M5": source_block},
        availability_times={"M5": timeframe_close_times(source_bars, "M5")},
    )
    return pd.concat([aligned, build_entry_idea_features(aligned)], axis=1)


@pytest.mark.parametrize("phase_mode", ["legacy", "reclaim_then_ifvg"])
def test_mtf_po3_candidate_waits_for_matching_ifvg_and_source_close(phase_mode: str) -> None:
    source_bars, sweeps, zones = _inputs()
    primary_index = pd.date_range(source_bars.index[0], periods=30, freq="1min")
    primary = pd.DataFrame({"close": np.full(len(primary_index), 100.0)}, index=primary_index)

    full = _aligned_candidate(source_bars, sweeps, zones, primary, phase_mode)
    candidate = full["entry_idea_po3_M5_long"]

    assert candidate.loc["2025-01-06 16:45:00+00:00"] == 0.0  # opposing IFVG only
    assert candidate.loc["2025-01-06 16:50:00+00:00"] == 0.0  # bull confirmation close
    assert candidate.loc["2025-01-06 16:54:00+00:00"] == 0.0  # post-confirmation source bar open
    assert candidate.loc["2025-01-06 16:55:00+00:00"] == 1.0  # next completed M5 bar

    source_state = _build_po3_timeframe_state(
        source_bars,
        sweeps,
        pd.DataFrame(index=source_bars.index),
        zones,
        phase_mode=phase_mode,
        max_ifvg_age_bars=50,
    )
    source_prefix = _build_po3_timeframe_state(
        source_bars.iloc[:4],
        sweeps.iloc[:4],
        pd.DataFrame(index=source_bars.index[:4]),
        zones.iloc[:4],
        phase_mode=phase_mode,
        max_ifvg_age_bars=50,
    )
    assert_frame_equal(source_state.iloc[:4], source_prefix, check_freq=False)

    primary_prefix = primary.iloc[:26]
    aligned_prefix = _aligned_candidate(source_bars, sweeps, zones, primary_prefix, phase_mode)
    assert_frame_equal(full.iloc[:26], aligned_prefix, check_freq=False)
