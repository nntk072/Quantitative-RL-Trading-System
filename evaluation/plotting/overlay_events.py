"""Compatibility exports for order-chart event geometry."""

from evaluation.plotting.orders.events import (
    OverlayEvents,
    SmtSegment,
    SweepLine,
    SwingRay,
    _align_origin_ts,
    _bar_pad,
    _rays_from_origins,
    _smt_segments,
    _sweep_lines,
    _swing_origins,
    build_overlay_events,
    candidate_sweep_line,
    confirmed_pivots,
)

__all__ = [
    "OverlayEvents",
    "SmtSegment",
    "SweepLine",
    "SwingRay",
    "_align_origin_ts",
    "_bar_pad",
    "_rays_from_origins",
    "_smt_segments",
    "_sweep_lines",
    "_swing_origins",
    "build_overlay_events",
    "candidate_sweep_line",
    "confirmed_pivots",
]
