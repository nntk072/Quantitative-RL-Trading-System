"""Boundary contracts for deriving chart events from price history."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from evaluation.plotting import overlay_events
from evaluation.plotting.chart_overlays import OverlayEvents, SweepLine
from evaluation.plotting.orders import events as order_events
from evaluation.plotting.overlay_events import (
    _sweep_lines,
    _swing_origins,
    build_overlay_events,
    candidate_sweep_line,
    confirmed_pivots,
)


def test_short_history_returns_empty_overlay_bundle() -> None:
    index = pd.date_range("2025-02-03 15:00", periods=6, freq="min")
    bars = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}, index=index)

    events = build_overlay_events(bars, swing_period=3)

    assert events.swings == []
    assert events.sweeps == []
    assert events.smt == []


def test_sweep_line_requires_a_prior_matching_pivot_and_a_crossing_wick() -> None:
    index = pd.date_range("2025-02-03 15:00", periods=5, freq="min")
    sweeps = pd.DataFrame(
        {
            "sweep_high": [0.0, 0.0, 1.0, 1.0, 1.0],
            "sweep_high_level": [np.nan, np.nan, 100.0, 102.0, 101.0],
            "sweep_high_wick": [np.nan, np.nan, 100.01, 102.5, 100.5],
        },
        index=index,
    )

    lines = _sweep_lines(
        index,
        sweeps,
        [(0, 100.0), (3, 101.0)],
        "high",
        pd.Timedelta("45s"),
    )

    assert len(lines) == 1
    assert lines[0].t0 == index[0]
    assert lines[0].t1 == index[2]
    assert lines[0].price == 100.0


def test_low_sweep_line_uses_prior_matching_low_and_rejects_non_crossing_wick() -> None:
    index = pd.date_range("2025-02-03 15:00", periods=4, freq="min", tz="UTC")
    sweeps = pd.DataFrame(
        {
            "sweep_low": [0.0, 1.0, 1.0, 0.0],
            "sweep_low_level": [np.nan, 99.0, 98.0, np.nan],
            "sweep_low_wick": [np.nan, 98.5, 98.5, np.nan],
        },
        index=index,
    )

    lines = _sweep_lines(index, sweeps, [(0, 99.0), (2, 98.0)], "low", pd.Timedelta("45s"))

    assert len(lines) == 1
    assert (lines[0].t0, lines[0].t1, lines[0].price, lines[0].side) == (
        index[0],
        index[1],
        99.0,
        "low",
    )


@pytest.mark.parametrize(
    ("pivot_time", "expected_origin"),
    [
        ("2025-02-03T15:01:00Z", 1),
        ("2025-02-03T15:20:00Z", 0),
        (None, 0),
    ],
)
def test_swing_origin_uses_nearby_source_time_or_confirmation_fallback(
    pivot_time: str | None, expected_origin: int
) -> None:
    index = pd.date_range("2025-02-03 15:00", periods=5, freq="min", tz="UTC")
    levels = pd.DataFrame(
        {
            "last_swing_high": [np.nan, np.nan, 105.0, 105.0, 105.0],
            "last_swing_high_time": [pd.NaT, pd.NaT, pivot_time, pivot_time, pivot_time],
        },
        index=index,
    )
    highs = pd.Series([101.0, 102.0, 105.0, 104.0, 103.0], index=index)

    origins = _swing_origins(levels, highs, index, 2, "high")

    assert origins == [(expected_origin, float(highs.iloc[expected_origin]))]


def test_confirmed_pivots_align_timezones_and_never_mark_outside_visible_bars() -> None:
    index = pd.date_range("2025-02-03 15:00", periods=3, freq="min", tz="UTC")
    events = OverlayEvents(
        swings=[
            overlay_events.SwingRay(index[0], index[2], 101.02, "high", origin=index[0]),
            overlay_events.SwingRay(index[1], index[2], 98.0, "low", origin=index[1]),
            overlay_events.SwingRay(
                index[0], index[2], 101.0, "high", origin=index[-1] + pd.Timedelta("5min")
            ),
        ]
    )
    bars = pd.DataFrame({"high": [101.0, 100.0, 100.0], "low": [99.0, 98.0, 99.0]}, index=index)

    confirmed = confirmed_pivots(events, bars, atol=0.05)

    assert [ray.mark_pivot for ray in confirmed.swings] == [True, True, False]
    assert confirmed.sweeps == events.sweeps
    assert confirmed.smt == events.smt
    assert confirmed_pivots(events, bars.iloc[:0]) is events


def test_build_overlay_events_falls_back_to_confirmation_minus_swing_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.date_range("2025-02-03 15:00", periods=6, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {
            "open": [100.0, 104.0, 103.0, 102.0, 101.0, 100.0],
            "high": [101.0, 105.0, 104.0, 103.0, 102.0, 101.0],
            "low": [99.0, 102.0, 101.0, 100.0, 99.0, 98.0],
            "close": [100.0, 104.0, 103.0, 102.0, 101.0, 100.0],
        },
        index=index,
    )
    levels = pd.DataFrame(
        {
            "last_swing_high": [np.nan, np.nan, np.nan, 105.0, 105.0, 105.0],
            "last_swing_high_time": [pd.NaT] * len(index),
            "last_swing_low": [np.nan] * len(index),
            "last_swing_low_time": [pd.NaT] * len(index),
        },
        index=index,
    )
    empty_sweeps = pd.DataFrame(
        {
            "sweep_high": [0.0] * len(index),
            "sweep_high_level": [np.nan] * len(index),
            "sweep_high_wick": [np.nan] * len(index),
            "sweep_low": [0.0] * len(index),
            "sweep_low_level": [np.nan] * len(index),
            "sweep_low_wick": [np.nan] * len(index),
        },
        index=index,
    )
    monkeypatch.setattr(order_events, "structure_levels", lambda *_args, **_kwargs: levels)
    monkeypatch.setattr(
        order_events,
        "detect_liquidity_sweeps",
        lambda *_args, **_kwargs: empty_sweeps,
    )

    events = build_overlay_events(bars, swing_period=2)

    assert len(events.swings) == 1
    swing = events.swings[0]
    assert (swing.side, swing.price) == ("high", 105.0)
    assert (swing.origin, swing.t0, swing.t1) == (index[1], index[1], index[-1])
    assert events.sweeps == []
    assert events.smt == []


def test_candidate_sweep_uses_exact_prior_wick_and_recorded_timeframe() -> None:
    index = pd.date_range("2025-02-03 15:00", periods=4, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {"high": [100.0, 101.0, 102.0, 103.0], "low": [99.0, 100.0, 101.0, 100.0]},
        index=index,
    )
    open_row = pd.Series(
        {
            "entry_setup_types": "['sweep']",
            "entry_origin_bar": 3,
            "direction": -1,
            "entry_setup_levels": {
                "sweep_high_level": 102.0,
                "sweep_high_pivot_bar": 2,
                "sweep_high_ref_tf_code": 60,
            },
        }
    )

    line = candidate_sweep_line(bars, open_row)

    assert line is not None
    assert (line.t0, line.t1, line.price, line.side, line.label) == (
        index[2],
        index[3],
        102.0,
        "high",
        "H1 liquidity sweep",
    )


def test_candidate_sweep_recovers_matching_recorded_event_when_snapshot_is_missing() -> None:
    index = pd.date_range("2025-02-03 15:00", periods=4, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {"high": [100.0, 101.0, 102.0, 101.0], "low": [99.0, 100.0, 101.0, 100.0]},
        index=index,
    )
    recorded = SweepLine(index[0], index[2], 102.0, "high", "M1 liquidity sweep")
    open_row = pd.Series(
        {
            "entry_setup_types": ["sweep"],
            "entry_origin_bar": 1,
            "direction": -1,
            "signal_time": index[3],
            "entry_setup_levels": {},
        }
    )

    line = candidate_sweep_line(bars, open_row, events=OverlayEvents(sweeps=[recorded]))

    assert line is recorded


def test_candidate_sweep_prefers_fired_feature_snapshot_and_normalizes_pivot_time() -> None:
    index = pd.date_range("2025-02-03 15:00", periods=4, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {"high": [100.0, 101.0, 100.0, 99.0], "low": [99.0, 98.0, 99.0, 97.0]},
        index=index,
    )
    features = pd.DataFrame(
        {
            "sweep_low": [0.0, 0.0, 0.0, 1.0],
            "sweep_low_level": [np.nan, np.nan, np.nan, 98.0],
            "sweep_low_pivot_time_ns": [np.nan, np.nan, np.nan, index[1].value],
            "sweep_low_ref_tf_code": [np.nan, np.nan, np.nan, 5.0],
        },
        index=index,
    )
    open_row = pd.Series({"entry_setup_types": "['sweep']", "entry_origin_bar": 3, "direction": 1})

    line = candidate_sweep_line(bars, open_row, features=features)

    assert line is not None
    assert (line.t0, line.t1, line.price, line.side, line.label) == (
        index[1],
        index[3],
        98.0,
        "low",
        "M5 liquidity sweep",
    )


def test_candidate_sweep_uses_latest_matching_event_before_signal_time() -> None:
    index = pd.date_range("2025-02-03 15:00", periods=5, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {"high": [100.0, 101.0, 102.0, 103.0, 104.0], "low": [99.0] * 5},
        index=index,
    )
    earlier = SweepLine(index[0], index[1], 100.0, "high", "M1 liquidity sweep")
    latest = SweepLine(index[0], index[2], 100.0, "high", "M5 liquidity sweep")
    after_signal = SweepLine(index[0], index[4], 100.0, "high", "H1 liquidity sweep")
    open_row = pd.Series(
        {
            "entry_setup_types": ["sweep"],
            "entry_origin_bar": 0,
            "direction": -1,
            "signal_time": "2025-02-03 15:03:00",
            "entry_setup_levels": "malformed snapshot",
        }
    )

    line = candidate_sweep_line(
        bars, open_row, events=OverlayEvents(sweeps=[earlier, latest, after_signal])
    )

    assert line is latest


@pytest.mark.parametrize(
    ("setup_types", "origin_bar", "direction"),
    [("malformed [", 2, -1), (["order_block"], 2, -1), (["sweep"], 7, -1), (["sweep"], 2, 0)],
)
def test_candidate_sweep_ignores_malformed_or_inapplicable_candidate_metadata(
    setup_types: object, origin_bar: object, direction: int
) -> None:
    index = pd.date_range("2025-02-03 15:00", periods=4, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {"high": [100.0, 101.0, 102.0, 103.0], "low": [99.0, 100.0, 101.0, 100.0]},
        index=index,
    )
    open_row = pd.Series(
        {"entry_setup_types": setup_types, "entry_origin_bar": origin_bar, "direction": direction}
    )

    assert candidate_sweep_line(bars, open_row) is None
