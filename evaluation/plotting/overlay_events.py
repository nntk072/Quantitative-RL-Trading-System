"""Swing, sweep, and SMT events for an order chart.

These are inputs to the window and to deviation levels. Drawing lives in
``chart_overlays``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from features.context.liquidity import detect_liquidity_sweeps
from features.context.smt import smt_divergence
from features.technical.structure import structure_levels

Side = Literal["high", "low"]


@dataclass(frozen=True)
class SwingRay:
    """Horizontal ray from a confirmed swing high/low going forward.

    ``origin`` is the pivot candle. ``t0`` is the visible start and may be
    later than ``origin`` after the ray is clipped to a chart window. The
    pivot dot is drawn only when ``origin`` still lies on the visible segment.
    """

    t0: pd.Timestamp
    t1: pd.Timestamp
    price: float
    side: Side
    origin: pd.Timestamp | None = None
    mark_pivot: bool = True

    def pivot_time(self) -> pd.Timestamp:
        """Candle that printed the swing, falling back to the visible start."""
        return self.origin if self.origin is not None else self.t0


@dataclass(frozen=True)
class SweepLine:
    """Horizontal line spanning the swept swing candle and the sweep candle."""

    t0: pd.Timestamp
    t1: pd.Timestamp
    price: float
    side: Side
    label: str


@dataclass(frozen=True)
class SmtSegment:
    """Line connecting two consecutive swing highs or two swing lows."""

    t0: pd.Timestamp
    p0: float
    t1: pd.Timestamp
    p1: float
    side: Side
    label: str


@dataclass
class OverlayEvents:
    """Structure events aligned to the bar index timezone."""

    swings: list[SwingRay] = field(default_factory=list)
    sweeps: list[SweepLine] = field(default_factory=list)
    smt: list[SmtSegment] = field(default_factory=list)

    def clip(self, start: pd.Timestamp, end: pd.Timestamp) -> OverlayEvents:
        """Keep events whose pivot candles lie inside ``[start, end]``.

        A swing that only passes through the window is dropped. Cutting it
        at the edge draws a dash that does not sit on its pivot. A sweep
        needs both ends on the chart. The forward end of a swing may still
        be trimmed to ``end`` so the ray does not leave the axis.
        """
        swings: list[SwingRay] = []
        for r in self.swings:
            origin = r.pivot_time()
            if origin < start or origin > end or r.t1 <= origin:
                continue
            t1 = min(r.t1, end)
            if t1 <= origin:
                continue
            swings.append(
                SwingRay(
                    t0=origin,
                    t1=t1,
                    price=r.price,
                    side=r.side,
                    origin=origin,
                    mark_pivot=r.mark_pivot,
                )
            )
        sweeps: list[SweepLine] = []
        for s in self.sweeps:
            if s.t0 < start or s.t1 > end or s.t1 <= s.t0:
                continue
            sweeps.append(s)
        smt: list[SmtSegment] = []
        for seg in self.smt:
            # Keep the segment only when both swing candles are on the chart.
            # Clipping a week-long line to the window edge leaves SMT off any candle.
            if seg.t0 < start or seg.t1 > end:
                continue
            smt.append(seg)
        return OverlayEvents(swings=swings, sweeps=sweeps, smt=smt)


def candidate_sweep_line(
    bars: pd.DataFrame,
    open_row: pd.Series,
    features: pd.DataFrame | None = None,
    events: OverlayEvents | None = None,
) -> SweepLine | None:
    """Return only the sweep that created this entry candidate, if recorded."""
    raw_types = open_row.get("entry_setup_types", ())
    if isinstance(raw_types, str):
        try:
            raw_types = ast.literal_eval(raw_types)
        except (SyntaxError, ValueError):
            raw_types = ()
    if not isinstance(raw_types, (list, tuple, set)) or "sweep" not in raw_types:
        return None
    origin_value = open_row.get("entry_origin_bar")
    if origin_value is None or pd.isna(origin_value):
        return None
    try:
        direction = int(float(open_row.get("direction", 0)))
        origin_bar = int(float(origin_value))
    except (TypeError, ValueError, OverflowError):
        return None
    if direction not in (-1, 1) or not 0 <= origin_bar < len(bars.index):
        return None
    side: Side = "low" if direction == 1 else "high"

    def matching_recorded_event() -> SweepLine | None:
        if events is None:
            return None
        index = pd.DatetimeIndex(bars.index)
        origin_time = pd.Timestamp(index[origin_bar])
        signal_value = open_row.get(
            "signal_time", open_row.get("decision_time", open_row.get("time"))
        )
        if signal_value is None or pd.isna(signal_value):
            return None
        try:
            signal_time = _align_origin_ts(pd.Timestamp(signal_value), index)
        except (TypeError, ValueError):
            return None
        matches = [
            event
            for event in events.sweeps
            if event.side == side and origin_time <= event.t1 <= signal_time
        ]
        if not matches:
            return None
        return max(matches, key=lambda event: event.t1)

    sweep_name = f"sweep_{side}"
    level_name = f"{sweep_name}_level"
    pivot_name = f"{sweep_name}_pivot_bar"
    tf_name = f"{sweep_name}_ref_tf_code"
    snapshot = open_row.get("entry_setup_levels", {})
    if isinstance(snapshot, str):
        try:
            snapshot = ast.literal_eval(snapshot)
        except (SyntaxError, ValueError):
            snapshot = {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}

    row: pd.Series | None = None
    if isinstance(features, pd.DataFrame) and origin_bar < len(features.index):
        row = features.iloc[origin_bar]
    level = snapshot.get(level_name)
    pivot_bar = snapshot.get(pivot_name)
    timeframe_code = snapshot.get(tf_name)
    if row is not None:
        try:
            fired = float(row.get(sweep_name, 0.0)) > 0.0
        except (TypeError, ValueError):
            fired = False
        if fired:
            level = row.get(level_name, level)
            pivot_ns = row.get(f"{sweep_name}_pivot_time_ns")
            if pivot_ns is not None and pd.notna(pivot_ns):
                try:
                    pivot_time = pd.Timestamp(int(float(pivot_ns)), unit="ns", tz="UTC")
                    index = pd.DatetimeIndex(bars.index)
                    if index.tz is None:
                        pivot_time = pivot_time.tz_localize(None)
                    else:
                        pivot_time = pivot_time.tz_convert(index.tz)
                    pivot_bar = index.get_indexer(pd.DatetimeIndex([pivot_time]), method="nearest")[
                        0
                    ]
                except (TypeError, ValueError, OverflowError):
                    pivot_bar = None
            if pivot_bar is None:
                fallback_pivot_time = row.get(f"last_swing_{side}_time")
                if fallback_pivot_time is not None and pd.notna(fallback_pivot_time):
                    try:
                        timestamp = pd.Timestamp(fallback_pivot_time)
                        index = pd.DatetimeIndex(bars.index)
                        if index.tz is None and timestamp.tzinfo is not None:
                            timestamp = timestamp.tz_localize(None)
                        elif index.tz is not None and timestamp.tzinfo is None:
                            timestamp = timestamp.tz_localize(index.tz)
                        elif index.tz is not None:
                            timestamp = timestamp.tz_convert(index.tz)
                        pivot_bar = index.get_indexer(
                            pd.DatetimeIndex([timestamp]), method="nearest"
                        )[0]
                    except (TypeError, ValueError, OverflowError):
                        pivot_bar = None
            timeframe_code = row.get(tf_name, timeframe_code)
    if level is None or pd.isna(level):
        return matching_recorded_event()
    try:
        level_value = float(level)
    except (TypeError, ValueError, OverflowError):
        return matching_recorded_event()
    if pivot_bar is None or pd.isna(pivot_bar):
        pivot_bar = -1
    try:
        pivot_index = int(float(pivot_bar))
    except (TypeError, ValueError, OverflowError):
        # Older trade ledgers do not persist a pivot bar. Recover it from the
        # exact source wick instead of dropping an otherwise recorded sweep.
        pivot_index = -1
    if not np.isfinite(level_value):
        return matching_recorded_event()
    wick_name = "low" if side == "low" else "high"
    wick_values = bars[wick_name].to_numpy(dtype=float)
    swept_wick = wick_values[origin_bar]
    crosses_level = swept_wick <= level_value if side == "low" else swept_wick >= level_value
    if not crosses_level:
        return matching_recorded_event()
    pivot_is_exact = 0 <= pivot_index < origin_bar and np.isclose(
        wick_values[pivot_index], level_value, atol=1e-8, rtol=0.0
    )
    if not pivot_is_exact:
        prior_wicks = np.flatnonzero(
            np.isclose(wick_values[:origin_bar], level_value, atol=1e-8, rtol=0.0)
        )
        if not len(prior_wicks):
            return matching_recorded_event()
        pivot_index = int(prior_wicks[-1])
    # Anchor the horizontal level to the actual wick values at both endpoints.
    # A nearby pivot timestamp or a tolerance-based match can otherwise leave
    # an orange sweep line visibly floating beside its source candle.
    level_value = float(wick_values[pivot_index])
    event_time = pd.Timestamp(bars.index[origin_bar])
    pivot_time = pd.Timestamp(bars.index[pivot_index])
    timeframe_by_code = {
        1: "M1",
        3: "M3",
        5: "M5",
        10: "M10",
        15: "M15",
        30: "M30",
        60: "H1",
        240: "H4",
        1440: "D1",
    }
    if timeframe_code is None or pd.isna(timeframe_code):
        timeframe_code = 1
    try:
        timeframe = timeframe_by_code.get(int(float(timeframe_code)), "M1")
    except (TypeError, ValueError, OverflowError):
        timeframe = "M1"
    return SweepLine(
        t0=pivot_time,
        t1=event_time,
        price=level_value,
        side=side,
        label=f"{timeframe} liquidity sweep",
    )


def _bar_pad(index: pd.DatetimeIndex) -> pd.Timedelta:
    """Extend sweep lines ~0.75 bars past each of the two candles."""
    if len(index) < 2:
        return pd.Timedelta("45s")
    delta = pd.Timedelta(index[1] - index[0])
    if delta <= pd.Timedelta(0):
        return pd.Timedelta("45s")
    return delta * 0.75


def _align_origin_ts(ts: pd.Timestamp, index: pd.DatetimeIndex) -> pd.Timestamp:
    """Match ``ts`` to the timezone of ``index``."""
    out = pd.Timestamp(ts)
    if index.tz is None:
        return out.tz_localize(None) if out.tzinfo is not None else out
    if out.tzinfo is None:
        return out.tz_localize(index.tz)
    return out.tz_convert(index.tz)


def _swing_origins(
    levels: pd.DataFrame,
    wick: pd.Series,
    index: pd.DatetimeIndex,
    swing_period: int,
    side: Side,
) -> list[tuple[int, float]]:
    """Pivot-bar origins: (swing-bar integer position, swing price).

    The pivot is ``last_swing_*_time`` on the bar where the level changes.
    ``confirmation_bar - swing_period`` is only the fallback when that time
    is missing.
    """
    pcol = "last_swing_high" if side == "high" else "last_swing_low"
    tcol = "last_swing_high_time" if side == "high" else "last_swing_low_time"
    changed = levels[pcol].ne(levels[pcol].shift()) & levels[pcol].notna()
    out: list[tuple[int, float]] = []
    flags = changed.to_numpy()
    prices = levels[pcol].to_numpy(dtype=float)
    times = levels[tcol] if tcol in levels.columns else None
    for i, flag in enumerate(flags):
        if not flag:
            continue
        price = float(prices[i])
        if np.isnan(price):
            continue
        origin_i = -1
        if times is not None and pd.notna(times.iloc[i]):
            ts = _align_origin_ts(pd.Timestamp(times.iloc[i]), index)
            loc = int(index.get_indexer(pd.Index([ts]), method="nearest")[0])
            if loc >= 0 and abs(pd.Timestamp(index[loc]) - ts) <= pd.Timedelta("1min"):
                origin_i = loc
        if origin_i < 0:
            origin_i = i - swing_period
        if origin_i < 0 or origin_i >= len(wick):
            continue
        # ``last_swing_*_time`` is the confirmed pivot's source candle, not its
        # later confirmation candle. Keep that exact wick location: searching
        # nearby candles for a similar price can attach the swing to the wrong
        # candle when multiple wicks are close or equal.
        draw_px = float(wick.iloc[origin_i])
        if not np.isfinite(draw_px):
            continue
        out.append((origin_i, draw_px))
    return out


def _rays_from_origins(
    index: pd.DatetimeIndex,
    origins: list[tuple[int, float]],
    side: Side,
    bars: pd.DataFrame,
) -> list[SwingRay]:
    last_i = len(index) - 1
    wick = bars["high" if side == "high" else "low"].to_numpy(dtype=float)
    next_cross = np.full(len(wick), len(wick), dtype=int)
    stack: list[int] = []
    for i in range(len(wick) - 1, -1, -1):
        while stack and (
            (wick[stack[-1]] < wick[i]) if side == "high" else (wick[stack[-1]] > wick[i])
        ):
            stack.pop()
        if stack:
            next_cross[i] = stack[-1]
        stack.append(i)
    rays: list[SwingRay] = []
    for origin_i, price in origins:
        candidate = int(next_cross[origin_i])
        end_i = candidate if candidate < len(wick) and candidate > origin_i else last_i
        origin_ts = pd.Timestamp(index[origin_i])
        rays.append(
            SwingRay(
                t0=origin_ts,
                t1=pd.Timestamp(index[end_i]),
                price=price,
                side=side,
                origin=origin_ts,
            )
        )
    return rays


def _sweep_lines(
    index: pd.DatetimeIndex,
    sweeps: pd.DataFrame,
    origins: list[tuple[int, float]],
    side: Side,
    pad: pd.Timedelta,
) -> list[SweepLine]:
    col = "sweep_high" if side == "high" else "sweep_low"
    lvl_col = "sweep_high_level" if side == "high" else "sweep_low_level"
    label = "Liquidity sweep"
    events = sweeps[col].to_numpy(dtype=float)
    levels = sweeps[lvl_col].to_numpy(dtype=float)
    wick = None
    if side == "high":
        wick = sweeps.get("sweep_high_wick")
    else:
        wick = sweeps.get("sweep_low_wick")
    lines: list[SweepLine] = []
    origin_i_arr = np.array([o[0] for o in origins], dtype=int)
    origin_prices = np.array([o[1] for o in origins], dtype=float)
    for i, fired in enumerate(events):
        if fired != 1.0:
            continue
        price = float(levels[i])
        if np.isnan(price):
            continue
        prior_mask = (origin_i_arr < i) & np.isclose(origin_prices, price, atol=1e-8, rtol=0.0)
        prior = origin_i_arr[prior_mask]
        # A sweep must connect to the candle that printed the level it took.
        # If that pivot is outside the available history, omit the misleading
        # line instead of attaching it to an unrelated recent swing.
        if not len(prior):
            continue
        origin_i = int(prior[-1])
        actual_sweep_wick = (
            float(wick.iloc[i])
            if isinstance(wick, pd.Series) and pd.notna(wick.iloc[i])
            else float("nan")
        )
        if np.isfinite(actual_sweep_wick):
            crosses_level = (
                actual_sweep_wick >= price if side == "high" else actual_sweep_wick <= price
            )
            if not crosses_level:
                continue
        # Use the exact source wick value after matching, keeping the line
        # attached to the wick despite floating-point serialization noise.
        price = float(origin_prices[np.flatnonzero(origin_i_arr == origin_i)[-1]])
        # Endpoints are the candles themselves. A time pad draws the X
        # between bars, off the wick the sweep took.
        t0 = pd.Timestamp(index[origin_i])
        t1 = pd.Timestamp(index[i])
        if t1 <= t0:
            t1 = t0 + pad * 2
        lines.append(SweepLine(t0=t0, t1=t1, price=price, side=side, label=label))
    return lines


def _smt_segments(
    index: pd.DatetimeIndex,
    smt: pd.DataFrame,
    origins: list[tuple[int, float]],
    prices: pd.Series,
    swing_period: int,
    side: Side,
) -> list[SmtSegment]:
    col = "smt_bearish" if side == "high" else "smt_bullish"
    label = "SMT divergence (M1)"
    flags = smt[col].to_numpy(dtype=float)
    segs: list[SmtSegment] = []
    origin_i_arr = np.array([o[0] for o in origins], dtype=int)
    for i, fired in enumerate(flags):
        if fired != 1.0:
            continue
        cur_i = i - swing_period
        if cur_i < 0:
            continue
        prior = origin_i_arr[origin_i_arr < cur_i]
        if len(prior) == 0:
            continue
        prev_i = int(prior[-1])
        segs.append(
            SmtSegment(
                t0=pd.Timestamp(index[prev_i]),
                p0=float(prices.iloc[prev_i]),
                t1=pd.Timestamp(index[cur_i]),
                p1=float(prices.iloc[cur_i]),
                side=side,
                label=label,
            )
        )
    return segs


def build_overlay_events(
    bars: pd.DataFrame,
    secondary: pd.DataFrame | None = None,
    swing_period: int = 5,
) -> OverlayEvents:
    """Compute swing rays, liquidity-sweep lines, and SMT segments on ``bars``."""
    if bars.empty or len(bars) < swing_period * 2 + 2:
        return OverlayEvents()
    idx = pd.DatetimeIndex(bars.index)
    pad = _bar_pad(idx)
    levels = structure_levels(bars, swing_period)
    sweeps = detect_liquidity_sweeps(bars, swing_period=swing_period)
    high_origins = _swing_origins(levels, bars["high"], idx, swing_period, "high")
    low_origins = _swing_origins(levels, bars["low"], idx, swing_period, "low")

    events = OverlayEvents(
        swings=_rays_from_origins(idx, high_origins, "high", bars)
        + _rays_from_origins(idx, low_origins, "low", bars),
        sweeps=_sweep_lines(idx, sweeps, high_origins, "high", pad)
        + _sweep_lines(idx, sweeps, low_origins, "low", pad),
    )
    if secondary is not None and not secondary.empty:
        smt = smt_divergence(bars, secondary, swing_period=swing_period)
        events.smt = _smt_segments(
            idx, smt, high_origins, bars["high"], swing_period, "high"
        ) + _smt_segments(idx, smt, low_origins, bars["low"], swing_period, "low")
    return events


def confirmed_pivots(
    events: OverlayEvents, bars: pd.DataFrame, atol: float = 0.05
) -> OverlayEvents:
    """Drop the pivot dot when that candle's high or low is not the ray price.

    The ray itself stays. A clipped window must not grow a dot on its first bar.
    """
    if bars.empty:
        return events
    idx = pd.DatetimeIndex(bars.index)
    swings: list[SwingRay] = []
    for ray in events.swings:
        origin = ray.pivot_time()
        ts = _align_origin_ts(origin, idx)
        loc = int(idx.get_indexer(pd.Index([ts]), method="nearest")[0])
        mark = False
        if loc >= 0 and abs(pd.Timestamp(idx[loc]) - ts) <= pd.Timedelta("1min"):
            col = "high" if ray.side == "high" else "low"
            mark = bool(np.isclose(float(bars[col].iloc[loc]), ray.price, atol=atol, rtol=0.0))
        swings.append(
            SwingRay(
                t0=ray.t0,
                t1=ray.t1,
                price=ray.price,
                side=ray.side,
                origin=origin,
                mark_pivot=mark,
            )
        )
    return OverlayEvents(swings=swings, sweeps=list(events.sweeps), smt=list(events.smt))
