"""Visible-window clipping and pivot markers for canonical chart events."""

from __future__ import annotations

import pandas as pd

from evaluation.plotting.orders.events import (
    OverlayEvents,
    SmtSegment,
    SweepLine,
    SwingRay,
    confirmed_pivots,
)


def test_overlay_clip_keeps_only_events_with_source_candles_in_window() -> None:
    index = pd.date_range("2025-02-03 15:00", periods=6, freq="min", tz="UTC")
    inside_swing = SwingRay(index[0], index[5], 105.0, "high", origin=index[2])
    crossing_swing = SwingRay(index[0], index[5], 99.0, "low", origin=index[0])
    zero_length_swing = SwingRay(index[3], index[3], 104.0, "high", origin=index[3])
    inside_sweep = SweepLine(index[1], index[2], 103.0, "high", "Liquidity sweep")
    outside_start_sweep = SweepLine(index[0], index[2], 102.0, "high", "Liquidity sweep")
    outside_end_sweep = SweepLine(index[2], index[4], 101.0, "low", "Liquidity sweep")
    reversed_sweep = SweepLine(index[3], index[2], 100.0, "low", "Liquidity sweep")
    inside_smt = SmtSegment(index[1], 100.0, index[3], 103.0, "high", "SMT divergence (M1)")
    crossing_start_smt = SmtSegment(index[0], 100.0, index[2], 102.0, "high", "SMT divergence (M1)")
    crossing_end_smt = SmtSegment(index[2], 102.0, index[4], 99.0, "low", "SMT divergence (M1)")
    events = OverlayEvents(
        swings=[inside_swing, crossing_swing, zero_length_swing],
        sweeps=[inside_sweep, outside_start_sweep, outside_end_sweep, reversed_sweep],
        smt=[inside_smt, crossing_start_smt, crossing_end_smt],
    )

    clipped = events.clip(index[1], index[3])

    assert clipped.swings == [
        SwingRay(index[2], index[3], 105.0, "high", origin=index[2], mark_pivot=True)
    ]
    assert clipped.sweeps == [inside_sweep]
    assert clipped.smt == [inside_smt]


def test_confirmed_pivots_keep_rays_but_mark_only_matching_source_wicks() -> None:
    index = pd.date_range("2025-02-03 15:00", periods=3, freq="min", tz="UTC")
    bars = pd.DataFrame({"high": [101.0, 100.0, 99.0], "low": [99.0, 98.0, 97.0]}, index=index)
    events = OverlayEvents(
        swings=[
            SwingRay(index[0], index[2], 101.2, "high", origin=index[0]),
            SwingRay(index[1], index[2], 98.0, "low", origin=index[1].tz_localize(None)),
        ]
    )

    confirmed = confirmed_pivots(events, bars)

    assert len(confirmed.swings) == 2
    assert [ray.mark_pivot for ray in confirmed.swings] == [False, True]
    assert [(ray.t0, ray.t1, ray.price, ray.side) for ray in confirmed.swings] == [
        (index[0], index[2], 101.2, "high"),
        (index[1], index[2], 98.0, "low"),
    ]
    assert [ray.origin for ray in confirmed.swings] == [
        index[0],
        index[1].tz_localize(None),
    ]
