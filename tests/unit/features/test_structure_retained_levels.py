"""Structure levels and retained swing levels: reference backend behavior and frame contract."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from features.technical.structure import structure_levels
from features.technical.swings import detect_pivots, detect_swings, retained_swing_levels

REPO = Path(__file__).resolve().parents[3]
EXAMPLE = REPO / "data" / "examples" / "US100.cash_M1_202412300105_202501020334.csv"


def _synthetic(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 18000.0 + np.cumsum(rng.normal(0.0, 0.8, n))
    open_ = np.concatenate([[close[0]], close[:-1]])
    wick = np.abs(rng.normal(0.0, 1.2, n))
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - wick
    index = pd.date_range("2025-01-02 00:00", periods=n, freq="1min", tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=index)


def _legacy_structure_levels(
    bars: pd.DataFrame, swing_period: int, atr_mult: float, retained_max: int = 8
) -> pd.DataFrame:
    """Oracle: the pre-kernel assembly of structure_levels (per-row time loops, list round trip)."""
    pivots = detect_pivots(bars, left=swing_period, right=swing_period)
    swings = detect_swings(bars, pivots, atr_mult=atr_mult)
    times = np.asarray(bars.index, dtype="datetime64[ns]")
    loc_h = swings["swing_high_location"].to_numpy(dtype=float)
    loc_l = swings["swing_low_location"].to_numpy(dtype=float)
    sh_times = np.full(len(bars), np.datetime64("NaT"), dtype="datetime64[ns]")
    sl_times = np.full(len(bars), np.datetime64("NaT"), dtype="datetime64[ns]")
    for i, loc in enumerate(loc_h):
        if np.isfinite(loc):
            sh_times[i] = times[int(loc)]
    for i, loc in enumerate(loc_l):
        if np.isfinite(loc):
            sl_times[i] = times[int(loc)]
    base = {
        "last_swing_high": swings["swing_high_extreme"].to_numpy(dtype=float),
        "last_swing_low": swings["swing_low_extreme"].to_numpy(dtype=float),
        "last_swing_high_time": pd.Series(sh_times, index=bars.index, dtype=bars.index.dtype),
        "last_swing_low_time": pd.Series(sl_times, index=bars.index, dtype=bars.index.dtype),
    }
    retained = {
        str(k): list(v)
        for k, v in retained_swing_levels(swings, bars, max_levels=retained_max)
        .to_dict("list")
        .items()
    }
    base.update(retained)
    return pd.DataFrame(base, index=bars.index)


@pytest.mark.parametrize("swing_period,atr_mult", [(2, 0.0), (3, 0.8), (5, 0.5)])
def test_structure_levels_frame_matches_legacy_assembly_exactly(
    swing_period: int, atr_mult: float
) -> None:
    bars = _synthetic(1500, seed=swing_period)
    result = structure_levels(bars, swing_period=swing_period, atr_mult=atr_mult)
    expected = _legacy_structure_levels(bars, swing_period, atr_mult)
    pd.testing.assert_frame_equal(result, expected, check_exact=True)


def test_structure_levels_on_tracked_example_keeps_schema_and_dtypes() -> None:
    frame = pd.read_csv(EXAMPLE, sep="\t", dtype=str).rename(columns=lambda n: n.strip("<>"))
    from market_data.arrow_schemas import mt5_export_to_bars

    table, problems = mt5_export_to_bars(frame, instrument_id="US100.cash", timeframe="M1")
    assert problems == []
    bars: pd.DataFrame = table.select(["event_time", "open", "high", "low", "close"]).to_pandas()
    bars.index = pd.DatetimeIndex(bars.pop("event_time"))
    result = structure_levels(bars, swing_period=3, atr_mult=0.8)
    assert result["last_swing_high_time"].dtype == bars.index.dtype
    assert result["n_retained_highs"].dtype == np.int64
    assert result["retained_high_1"].dtype == np.float64
    pd.testing.assert_frame_equal(result, _legacy_structure_levels(bars, 3, 0.8), check_exact=True)


def test_retained_backend_defaults_to_the_python_reference() -> None:
    bars = _synthetic(300, seed=9)
    pivots = detect_pivots(bars, left=3, right=3)
    swings = detect_swings(bars, pivots, atr_mult=0.8)
    default = retained_swing_levels(swings, bars, max_levels=4)
    explicit = retained_swing_levels(swings, bars, max_levels=4, backend="python")
    pd.testing.assert_frame_equal(default, explicit, check_exact=True)


def test_unknown_retained_backend_is_refused() -> None:
    bars = _synthetic(20, seed=1)
    pivots = detect_pivots(bars, left=2, right=2)
    swings = detect_swings(bars, pivots, atr_mult=0.0)
    with pytest.raises(ValueError, match="unknown retained-level backend"):
        retained_swing_levels(swings, bars, backend="numba")
