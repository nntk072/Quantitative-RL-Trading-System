"""Entry-to-exit position box and candle-anchored MAE/MFE/SL/TP."""

from __future__ import annotations

import ast
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from numbers import Real
from typing import Any, cast

import numpy as np
import pandas as pd

from evaluation.metrics.candle_quality import tradable_mask
from evaluation.metrics.trades import TradeChartMetrics
from evaluation.plotting.chart_levels import (
    chart_ylim,
    level_near_candles,
)
from evaluation.plotting.overlay_events import OverlayEvents
from evaluation.reporting.trade_note import pretty_ref
from features.context.swing_retracement import SWING_LEVELS, level_token
from trading.orders.levels import DEVIATION_KS

_ENTRY_LINE = "#546e7a"
_RED = "#e53935"
_GREEN = "#2e7d32"
_MAE = "#ef9a9a"
_MFE = "#a5d6a7"


@dataclass
class LevelSeg:
    """Horizontal segment tied to a candle when one exists."""

    label: str
    price: float
    t0: pd.Timestamp
    t1: pd.Timestamp
    color: str
    linestyle: str
    mark: pd.Timestamp | None = None


@dataclass
class ZoneBand:
    """A causal feature zone displayed over its active chart interval."""

    label: str
    low: float
    high: float
    t0: pd.Timestamp
    t1: pd.Timestamp
    color: str

    @property
    def midpoint(self) -> float:
        return (self.low + self.high) / 2.0


@dataclass
class OrderLevels:
    """Geometry for the position box. Far targets stay out of ``ylim``."""

    ylim: tuple[float, float]
    t_open: pd.Timestamp
    t_close: pd.Timestamp
    entry: float
    direction: int
    exit_price: float
    red: tuple[float, float] | None = None
    green: tuple[float, float] | None = None
    segs: list[LevelSeg] = field(default_factory=list)
    deviations: list[tuple[float, float]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    offset: float = 1.0
    manip_spans: list[tuple[pd.Timestamp, pd.Timestamp]] = field(default_factory=list)
    manip_ends: list[pd.Timestamp] = field(default_factory=list)
    distribution_spans: list[tuple[pd.Timestamp, pd.Timestamp]] = field(default_factory=list)
    off_chart_levels: list[tuple[str, float, str]] = field(default_factory=list)
    zones: list[ZoneBand] = field(default_factory=list)


def _feature_zones(
    features: pd.DataFrame,
    window: pd.DataFrame,
    open_row: pd.Series,
    *,
    order_block_timeframes: tuple[str, ...],
    fvg_timeframes: tuple[str, ...],
    ifvg_timeframes: tuple[str, ...],
    entry_idea_plot_config: dict[str, Any] | None = None,
) -> list[ZoneBand]:
    """Plot only the live, side-matched zones linked to this trade's ideas."""

    def parse(raw: Any, default: Any) -> Any:
        if isinstance(raw, str):
            try:
                return ast.literal_eval(raw)
            except (SyntaxError, ValueError):
                return default
        return raw if raw is not None else default

    def tf_values(raw: Any) -> tuple[str, ...]:
        value = raw
        if isinstance(raw, str):
            try:
                value = ast.literal_eval(raw)
            except (SyntaxError, ValueError):
                value = raw
        if isinstance(value, str):
            value = (value,)
        return (
            tuple(str(tf).upper() for tf in value) if isinstance(value, (list, tuple, set)) else ()
        )

    aligned = features.reindex(window.index)
    idea_field_present = "entry_ideas" in open_row.index
    ideas_raw = parse(open_row.get("entry_ideas"), ())
    ideas = set(ideas_raw) if isinstance(ideas_raw, (list, tuple, set)) else set()
    timeframe_map = parse(open_row.get("entry_idea_timeframes"), {})
    if not isinstance(timeframe_map, Mapping):
        timeframe_map = {}

    recorded_zones = parse(open_row.get("entry_idea_zones"), None)
    selected: list[dict[str, Any]] = []
    if isinstance(recorded_zones, list):
        selected = [
            {str(key): value for key, value in item.items()}
            for item in recorded_zones
            if isinstance(item, Mapping)
        ]
    elif idea_field_present:
        direction_value = open_row.get("direction", 0)
        try:
            long_trade = float(direction_value) > 0.0
        except (TypeError, ValueError):
            long_trade = str(direction_value).lower() in {"long", "buy", "1"}
        side = "bull" if long_trade else "bear"
        family_by_idea = {
            "po3": ("fvg", "ifvg"),
            "order_block": ("ob",),
            "standard_deviation": (),
            "fvg_retest": ("fvg", "ifvg"),
        }
        for idea in ideas:
            for tf in tf_values(timeframe_map.get(idea, ("M1",))):
                for family in family_by_idea.get(str(idea), ()):
                    selected.append({"idea": idea, "family": family, "timeframe": tf, "side": side})
    else:
        # Historical runs without idea attribution retain explicit chart toggles.
        for family, timeframes in (
            ("ob", order_block_timeframes),
            ("fvg", fvg_timeframes),
            ("ifvg", ifvg_timeframes),
        ):
            for tf in timeframes:
                for side in ("bull", "bear"):
                    selected.append({"family": family, "timeframe": tf, "side": side})

    labels = {
        "ob": ("Order Block", "#2e7d32"),
        "fvg": ("Fair Value Gap", "#1976d2"),
        "ifvg": ("Inverse Fair Value Gap", "#ef6c00"),
    }
    zones: list[ZoneBand] = []
    index = pd.DatetimeIndex(aligned.index)
    open_value = open_row.get("time")
    if open_value is None or pd.isna(open_value):
        anchor = len(index) - 1
    else:
        stamp = pd.Timestamp(open_value)
        if index.tz is None and stamp.tzinfo is not None:
            stamp = stamp.tz_localize(None)
        elif index.tz is not None:
            stamp = (
                stamp.tz_localize(index.tz) if stamp.tzinfo is None else stamp.tz_convert(index.tz)
            )
        anchor = int(index.searchsorted(stamp, side="right") - 1)
    if anchor < 0 or anchor >= len(index):
        return zones

    for item in selected:
        idea = str(item.get("idea", "")).lower()
        family = str(item.get("family", "")).lower()
        timeframe = str(item.get("timeframe", "M1")).upper()
        side = str(item.get("side", "")).lower()
        if family not in labels or side not in {"bull", "bear"}:
            continue
        idea_settings = (entry_idea_plot_config or {}).get(idea, {})
        if idea and isinstance(idea_settings, Mapping):
            if not bool(idea_settings.get("enabled", True)):
                continue
            show_key = {"ob": "show_zone", "fvg": "show_fvg", "ifvg": "show_ifvg"}[family]
            if not bool(idea_settings.get(show_key, True)):
                continue
            configured_tfs = idea_settings.get("timeframes")
            if configured_tfs is not None and timeframe not in set(tf_values(configured_tfs)):
                continue
        prefix = "" if timeframe == "M1" and family in {"ob", "ifvg"} else f"{timeframe}_"
        stem = f"{family}_{side}"
        active_col = f"{prefix}{stem}_active"
        low_col = f"{prefix}{stem}_low"
        high_col = f"{prefix}{stem}_high"
        if not {active_col, low_col, high_col}.issubset(aligned.columns):
            continue
        active = pd.to_numeric(aligned[active_col], errors="coerce").fillna(0.0).to_numpy() > 0.0
        lows = pd.to_numeric(aligned[low_col], errors="coerce").to_numpy(dtype=float)
        highs = pd.to_numeric(aligned[high_col], errors="coerce").to_numpy(dtype=float)
        saved_low = item.get("low")
        saved_high = item.get("high")
        try:
            zone_low = float(saved_low) if saved_low is not None else float(lows[anchor])
            zone_high = float(saved_high) if saved_high is not None else float(highs[anchor])
        except (TypeError, ValueError):
            continue
        if not np.isfinite(zone_low + zone_high) or zone_low > zone_high:
            continue
        same_zone = (
            active
            & np.isclose(lows, zone_low, rtol=1e-9, atol=1e-6)
            & np.isclose(highs, zone_high, rtol=1e-9, atol=1e-6)
        )
        positions = np.flatnonzero(same_zone)
        if len(positions):
            t0, t1 = pd.Timestamp(index[positions[0]]), pd.Timestamp(index[positions[-1]])
            if family == "ob":
                origin_column = f"{prefix}{stem}_origin_time_ms"
                if origin_column in aligned.columns:
                    try:
                        origin_ms = float(aligned[origin_column].iloc[positions[0]])
                        if np.isfinite(origin_ms):
                            origin = pd.Timestamp(int(origin_ms), unit="ms", tz="UTC")
                            t0 = (
                                origin.tz_localize(None)
                                if index.tz is None
                                else origin.tz_convert(index.tz)
                            )
                    except (TypeError, ValueError, OverflowError):
                        pass
        else:
            start_ns = item.get("start_time_ns")
            try:
                if start_ns is None:
                    raise ValueError("zone start time is missing")
                start_time = pd.Timestamp(int(start_ns), unit="ns", tz="UTC")
                if index.tz is None:
                    start_time = start_time.tz_localize(None)
                else:
                    start_time = start_time.tz_convert(index.tz)
                t0 = max(pd.Timestamp(index[0]), start_time)
            except (TypeError, ValueError, OverflowError):
                t0 = pd.Timestamp(index[anchor])
            t1 = pd.Timestamp(index[-1])
        label, color = labels[family]
        if family == "ob" and side == "bear":
            color = "#c62828"
        idea = str(item.get("idea", ""))
        idea_prefix = (
            "PO3 · " if idea == "po3" else f"{idea.replace('_', ' ').upper()} · " if idea else ""
        )
        zones.append(
            ZoneBand(
                label=f"{idea_prefix}{timeframe} {side.title()} {label}",
                low=zone_low,
                high=zone_high,
                t0=t0,
                t1=t1,
                color=color,
            )
        )
    return zones


def _feature_swing_segments(
    features: pd.DataFrame,
    window: pd.DataFrame,
    timeframes: tuple[str, ...],
    lower_timeframe_swings: tuple[object, ...] = (),
) -> list[LevelSeg]:
    """Draw selected aligned MTF swing levels, preferring lower TF duplicates."""
    ladder = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
    rank = {timeframe: index for index, timeframe in enumerate(ladder)}
    aligned = features.reindex(window.index)
    segments: list[LevelSeg] = []
    for timeframe in sorted(
        {str(value).upper() for value in timeframes if str(value).upper() != "M1"},
        key=lambda value: rank.get(value, len(rank)),
    ):
        prefix = f"{timeframe}_"
        for side, color in (("high", "#8e24aa"), ("low", "#00838f")):
            column = f"{prefix}last_swing_{side}"
            if column not in aligned.columns:
                continue
            values = pd.to_numeric(aligned[column], errors="coerce").to_numpy(dtype=float)
            start: int | None = None
            current: float | None = None
            for idx in range(len(aligned) + 1):
                value = (
                    float(values[idx]) if idx < len(values) and np.isfinite(values[idx]) else None
                )
                if value != current:
                    if start is not None and current is not None:
                        t0 = pd.Timestamp(aligned.index[start])
                        t1 = pd.Timestamp(aligned.index[max(start, idx - 1)])
                        overlaps_lower = any(
                            existing.label.endswith(f"Swing {side.title()}")
                            and max(t0, existing.t0) <= min(t1, existing.t1)
                            and abs(current - existing.price) <= 0.5
                            for existing in segments
                        )
                        overlaps_lower = overlaps_lower or any(
                            getattr(ray, "side", None) == side
                            and max(t0, pd.Timestamp(getattr(ray, "t0")))
                            <= min(t1, pd.Timestamp(getattr(ray, "t1")))
                            and abs(current - float(getattr(ray, "price"))) <= 0.5
                            for ray in lower_timeframe_swings
                        )
                        if not overlaps_lower:
                            segments.append(
                                LevelSeg(
                                    label=f"{timeframe} Swing {side.title()}",
                                    price=current,
                                    t0=t0,
                                    t1=t1,
                                    color=color,
                                    linestyle="--",
                                )
                            )
                    start = idx if value is not None else None
                    current = value
    return segments


def _active_swing(events: OverlayEvents, t: pd.Timestamp, side: str) -> float | None:
    best_t: pd.Timestamp | None = None
    best_p: float | None = None
    for ray in events.swings:
        if ray.side != side:
            continue
        origin = ray.pivot_time()
        if origin <= t <= ray.t1 and (best_t is None or origin >= best_t):
            best_t = origin
            best_p = ray.price
    return best_p


def _candle_bounds(window: pd.DataFrame) -> tuple[float, float]:
    mask = tradable_mask(window)
    good = window.loc[mask] if mask.any() else window
    return float(good["low"].min()), float(good["high"].max())


def _in_window(ts: pd.Timestamp | None, window: pd.DataFrame) -> bool:
    if ts is None or window.empty:
        return False
    idx = pd.DatetimeIndex(window.index)
    loc = int(idx.get_indexer(pd.Index([pd.Timestamp(ts)]), method="nearest")[0])
    if loc < 0:
        return False
    return abs(pd.Timestamp(idx[loc]) - pd.Timestamp(ts)) <= pd.Timedelta("1min")


def _on_chart(
    price: float | None, when: pd.Timestamp | None, window: pd.DataFrame, lo: float, hi: float
) -> bool:
    if price is None:
        return False
    if _in_window(when, window):
        return True
    return level_near_candles(float(price), lo, hi)


def _finite_at(frame: pd.DataFrame, column: str, when: pd.Timestamp) -> float | None:
    if column not in frame.columns:
        return None
    if when not in frame.index:
        return None
    value = frame.at[when, column]
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _optional_text(value: Any) -> str:
    """Return an empty string for null chart metadata without truth-testing NA."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _feature_position(frame: pd.DataFrame, when: object) -> int | None:
    if frame.empty or not isinstance(frame.index, pd.DatetimeIndex):
        return None
    stamp = pd.Timestamp(cast(Any, when))
    if frame.index.tz is None and stamp.tzinfo is not None:
        stamp = stamp.tz_localize(None)
    elif frame.index.tz is not None:
        stamp = (
            stamp.tz_localize(frame.index.tz)
            if stamp.tzinfo is None
            else stamp.tz_convert(frame.index.tz)
        )
    position = int(frame.index.searchsorted(stamp, side="right") - 1)
    return position if 0 <= position < len(frame) else None


def _idea_context(open_row: pd.Series) -> tuple[set[str], Mapping[str, Any]]:
    raw_ideas = open_row.get("entry_ideas", ())
    if isinstance(raw_ideas, str):
        try:
            raw_ideas = ast.literal_eval(raw_ideas)
        except (SyntaxError, ValueError):
            raw_ideas = ()
    ideas = set(raw_ideas) if isinstance(raw_ideas, (list, tuple, set)) else set()
    raw_timeframes = open_row.get("entry_idea_timeframes", {})
    if isinstance(raw_timeframes, str):
        try:
            raw_timeframes = ast.literal_eval(raw_timeframes)
        except (SyntaxError, ValueError):
            raw_timeframes = {}
    return ideas, raw_timeframes if isinstance(raw_timeframes, Mapping) else {}


def _selected_timeframes(open_row: pd.Series, idea: str) -> tuple[str, ...]:
    ideas, timeframe_map = _idea_context(open_row)
    if "entry_ideas" in open_row.index and idea not in ideas:
        return ()
    raw = timeframe_map.get(idea, ("M1",))
    if isinstance(raw, str):
        raw = (raw,)
    if not isinstance(raw, (tuple, list, set)):
        return ()
    return tuple(str(value).upper() for value in raw)


def _retracement_segments(
    features: pd.DataFrame,
    window: pd.DataFrame,
    open_row: pd.Series,
    t_open: pd.Timestamp,
    t_close: pd.Timestamp,
    candle_lo: float,
    candle_hi: float,
    entry_idea_plot_config: dict[str, Any] | None = None,
) -> list[LevelSeg]:
    """Draw configured Fib-like swing levels only on attributed trades."""
    settings = (entry_idea_plot_config or {}).get("standard_deviation", {})
    timeframes = _selected_timeframes(open_row, "standard_deviation")
    swing_reference = " ".join(
        _optional_text(open_row.get(key, "")) for key in ("sl_ref", "tp_ref")
    ).lower()
    if not timeframes and any(
        marker in swing_reference for marker in ("standard_deviation_level_", "dev_", "swing")
    ):
        defaults = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
        timeframes = _as_timeframes(
            settings.get("timeframes", defaults) if isinstance(settings, Mapping) else defaults
        )
    if not timeframes:
        return []
    if isinstance(settings, Mapping):
        if not bool(settings.get("enabled", True)):
            return []
        configured_tfs = settings.get("timeframes")
        if configured_tfs is not None:
            allowed = set(_as_timeframes(configured_tfs))
            timeframes = tuple(tf for tf in timeframes if tf in allowed)
        raw_levels = settings.get("levels", SWING_LEVELS)
        levels = tuple(float(value) for value in raw_levels)
        max_range_fraction = float(settings.get("max_chart_range_fraction", 0.15))
    else:
        levels = SWING_LEVELS
        max_range_fraction = 0.15
    if not timeframes:
        return []
    position = _feature_position(features, t_open)
    if position is None:
        return []
    span = max(candle_hi - candle_lo, 1e-6)
    near = max(0.0, max_range_fraction) * span
    index = pd.DatetimeIndex(features.index)
    segments: list[LevelSeg] = []
    seen_prices: list[float] = []
    ladder = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
    rank = {timeframe: index for index, timeframe in enumerate(ladder)}
    for timeframe in sorted(set(timeframes), key=lambda tf: rank.get(tf, len(rank))):
        prefix = "" if timeframe == "M1" else f"{timeframe}_"
        start_col = f"{prefix}standard_deviation_leg_start_time_ns"
        end_col = f"{prefix}standard_deviation_leg_end_time_ns"
        start_ns = _finite_at(features, start_col, index[position])
        end_ns = _finite_at(features, end_col, index[position])
        if start_ns is None or end_ns is None:
            continue
        start_utc = pd.Timestamp(int(start_ns), unit="ns", tz="UTC")
        end_utc = pd.Timestamp(int(end_ns), unit="ns", tz="UTC")
        if index.tz is None:
            start_time = start_utc.tz_localize(None)
            end_time = end_utc.tz_localize(None)
        else:
            start_time = start_utc.tz_convert(index.tz)
            end_time = end_utc.tz_convert(index.tz)
        if end_time > t_open or start_time > t_close:
            continue
        segment_start = max(pd.Timestamp(window.index[0]), start_time)
        segment_end = min(pd.Timestamp(window.index[-1]), t_close)
        if segment_start > segment_end:
            continue
        for level in levels:
            column = f"{prefix}standard_deviation_level_{level_token(level)}_price"
            price = _finite_at(features, column, index[position])
            if price is None or not candle_lo - near <= price <= candle_hi + near:
                continue
            if any(abs(price - existing) <= 0.5 for existing in seen_prices):
                continue
            seen_prices.append(price)
            segments.append(
                LevelSeg(
                    label=f"Fib/SD: {level:g} ({timeframe})",
                    price=price,
                    t0=segment_start,
                    t1=segment_end,
                    color="#ad1457",
                    linestyle="--",
                )
            )
    return segments


def _stamp(ts: object) -> pd.Timestamp:
    if isinstance(ts, pd.Timestamp):
        return ts
    return pd.Timestamp(str(ts))


def _as_timeframes(raw: Any) -> tuple[str, ...]:
    """Normalize a YAML/list/scalar timeframe setting for chart filters."""
    if isinstance(raw, str):
        raw = (raw,)
    if not isinstance(raw, (tuple, list, set)):
        return ()
    return tuple(str(value).upper() for value in raw)


def _manipulation_marks(
    features: pd.DataFrame,
    window: pd.DataFrame,
    t_open: pd.Timestamp,
    t_close: pd.Timestamp,
    direction: int,
    open_row: pd.Series,
    entry_idea_plot_config: dict[str, Any] | None = None,
) -> tuple[
    list[tuple[pd.Timestamp, pd.Timestamp]],
    list[pd.Timestamp],
    list[tuple[pd.Timestamp, pd.Timestamp]],
    list[LevelSeg],
]:
    """Return PO3 manipulation and distribution context for attributed TFs."""
    observed_position = _feature_position(features, t_open)
    if observed_position is None:
        return [], [], [], []
    observed_features = features.iloc[: observed_position + 1]
    aligned = observed_features.reindex(window.index)
    timeframes = _selected_timeframes(open_row, "po3")
    if "entry_ideas" not in open_row.index:
        timeframes = ("M1",)
    manip_spans: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    distribution_spans: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    ends: list[pd.Timestamp] = []
    segs: list[LevelSeg] = []
    legacy_row = "entry_ideas" not in open_row.index
    settings = (entry_idea_plot_config or {}).get("po3", {})
    if isinstance(settings, Mapping):
        if not bool(settings.get("enabled", True)):
            return manip_spans, ends, distribution_spans, segs
        configured_tfs = settings.get("timeframes")
        if configured_tfs is not None:
            allowed = set(_as_timeframes(configured_tfs))
            timeframes = tuple(tf for tf in timeframes if tf in allowed)
        show_manipulation = bool(settings.get("show_manipulation", True))
        show_distribution = bool(settings.get("show_distribution", True))
    else:
        show_manipulation = show_distribution = True
    if not timeframes:
        return manip_spans, ends, distribution_spans, segs
    for timeframe in timeframes:
        prefix = "" if timeframe == "M1" else f"{timeframe}_"
        active_col = f"{prefix}po3_manipulation_active"
        distribution_col = f"{prefix}po3_distribution"
        if active_col not in aligned.columns:
            continue

        def spans_for(column: str, destination: list[tuple[pd.Timestamp, pd.Timestamp]]) -> None:
            if column not in aligned.columns:
                return
            values = pd.to_numeric(aligned[column], errors="coerce").fillna(0.0).to_numpy() > 0.0
            start: int | None = None
            for index, active in enumerate(np.append(values, False)):
                if active and start is None:
                    start = index
                elif not active and start is not None:
                    end_index = index - 1
                    destination.append(
                        (pd.Timestamp(aligned.index[start]), pd.Timestamp(aligned.index[end_index]))
                    )
                    start = None

        if show_manipulation:
            spans_for(active_col, manip_spans)
        if show_distribution:
            spans_for(distribution_col, distribution_spans)
        end_col = f"{prefix}po3_manipulation_end"
        if show_manipulation and end_col in aligned.columns:
            ended = pd.to_numeric(aligned[end_col], errors="coerce").fillna(0.0).to_numpy() > 0.0
            ends.extend(pd.Timestamp(aligned.index[i]) for i in np.flatnonzero(ended))

        level_names = (
            (("high", "manip high"), ("low", "manip low"))
            if legacy_row
            else (("high", "manipulation high"), ("low", "manipulation low"))
        )
        for suffix, label in level_names if show_manipulation else ():
            price_col = f"{prefix}po3_manipulation_{suffix}"
            position = _feature_position(features, t_open)
            price = (
                float(pd.to_numeric(features[price_col], errors="coerce").iloc[position])
                if position is not None and price_col in features
                else float("nan")
            )
            if np.isfinite(price):
                segs.append(
                    LevelSeg(
                        f"PO3 {timeframe} {label}" if not legacy_row else label,
                        price,
                        pd.Timestamp(window.index[0]),
                        t_close,
                        "#6a1b9a",
                        "--",
                    )
                )
        if legacy_row and timeframe == "M1":
            for column, label in (
                ("asian_high", "Asian high"),
                ("asian_low", "Asian low"),
                ("london_high", "London high"),
                ("london_low", "London low"),
                ("sweep_low_level" if direction == 1 else "sweep_high_level", "sweep"),
            ):
                legacy_price = _finite_at(aligned, column, t_open)
                if legacy_price is not None:
                    segs.append(LevelSeg(label, legacy_price, t_open, t_close, "#6a1b9a", "--"))
    return manip_spans, ends, distribution_spans, segs


def order_levels(
    window: pd.DataFrame,
    metrics: TradeChartMetrics,
    events: OverlayEvents,
    bars: pd.DataFrame,
    t_open: pd.Timestamp,
    t_close: pd.Timestamp,
    open_row: pd.Series,
    *,
    show_mae_mfe: bool = True,
    show_sl_tp: bool = True,
    features: pd.DataFrame | None = None,
    order_block_timeframes: tuple[str, ...] = (),
    fvg_timeframes: tuple[str, ...] = (),
    ifvg_timeframes: tuple[str, ...] = (),
    swing_timeframes: tuple[str, ...] = ("M1",),
    entry_idea_plot_config: dict[str, Any] | None = None,
) -> OrderLevels:
    """Position box, segments, and notes. A far RR target does not set the axis."""
    lo, hi = _candle_bounds(window)
    span = max(hi - lo, 1e-6)
    offset = max(span * 0.015, 0.5)
    segs: list[LevelSeg] = []
    if features is not None:
        lower_swings = (
            tuple(events.swings) if "M1" in {str(tf).upper() for tf in swing_timeframes} else ()
        )
        segs.extend(_feature_swing_segments(features, window, swing_timeframes, lower_swings))
        segs.extend(
            _retracement_segments(
                features,
                window,
                open_row,
                t_open,
                t_close,
                lo,
                hi,
                entry_idea_plot_config,
            )
        )
    zones = (
        _feature_zones(
            features,
            window,
            open_row,
            order_block_timeframes=order_block_timeframes,
            fvg_timeframes=fvg_timeframes,
            ifvg_timeframes=ifvg_timeframes,
            entry_idea_plot_config=entry_idea_plot_config,
        )
        if features is not None
        else []
    )
    off_chart_levels: list[tuple[str, float, str]] = []
    extra: list[float] = [metrics.entry_price, metrics.exit_price]

    if (
        show_mae_mfe
        and metrics.mae_drawn
        and _on_chart(metrics.mae_price, metrics.mae_time, window, lo, hi)
    ):
        segs.append(
            LevelSeg(
                "MAE", metrics.mae_price, t_open, metrics.mae_time, _MAE, "--", metrics.mae_time
            )
        )
        extra.append(metrics.mae_price)
    if (
        show_mae_mfe
        and metrics.mfe_drawn
        and _on_chart(metrics.mfe_price, metrics.mfe_time, window, lo, hi)
    ):
        segs.append(
            LevelSeg(
                "MFE", metrics.mfe_price, t_open, metrics.mfe_time, _MFE, "--", metrics.mfe_time
            )
        )
        extra.append(metrics.mfe_price)

    sl_ref = _optional_text(open_row.get("sl_ref", ""))
    tp_ref = _optional_text(open_row.get("tp_ref", ""))
    exit_mode = _optional_text(open_row.get("exit_mode", ""))
    planned = open_row.get("planned_rr")
    planned_txt = ""
    if planned is not None and pd.notna(planned):
        planned_txt = f" ({float(planned):.2f}R)"
    sl_label = f"Stop loss (SL) - {pretty_ref(sl_ref)}" if sl_ref else "Stop loss (SL)"
    tp_label = (
        f"Take profit (TP) - {pretty_ref(tp_ref)}{planned_txt}"
        if tp_ref
        else f"Take profit (TP){planned_txt}"
    )
    ema_exit = exit_mode == "ema_21" or tp_ref == "ema_21"

    sl_on = show_sl_tp and _on_chart(metrics.sl_price, metrics.sl_time, window, lo, hi)
    tp_on = (
        show_sl_tp and not ema_exit and _on_chart(metrics.tp_price, metrics.tp_time, window, lo, hi)
    )
    if sl_on and metrics.sl_price is not None:
        segs.append(
            LevelSeg(sl_label, metrics.sl_price, t_open, t_close, _RED, ":", metrics.sl_time)
        )
        extra.append(metrics.sl_price)
    elif show_sl_tp and metrics.sl_price is not None:
        off_chart_levels.append((sl_label, metrics.sl_price, _RED))
    if tp_on and metrics.tp_price is not None:
        segs.append(
            LevelSeg(tp_label, metrics.tp_price, t_open, t_close, _GREEN, ":", metrics.tp_time)
        )
        extra.append(metrics.tp_price)
    elif show_sl_tp and not ema_exit and metrics.tp_price is not None:
        off_chart_levels.append((tp_label, metrics.tp_price, _GREEN))

    notes: list[str] = []
    selected_deviations: set[float] = set()
    selected_swing_level_columns: set[str] = set()
    for reference in (sl_ref, tp_ref):
        for token in reference.split("|"):
            if "standard_deviation_level_" in token and token.endswith("_price"):
                selected_swing_level_columns.add(token)
            if "dev_" not in token:
                continue
            try:
                selected_deviations.add(float(token.rsplit("dev_", 1)[1]))
            except ValueError:
                continue
    deviations: list[tuple[float, float]] = []
    for column in sorted(selected_swing_level_columns):
        if features is None:
            continue
        price = _finite_at(features, column, t_open)
        if price is None:
            continue
        level_token_value = column.rsplit("standard_deviation_level_", 1)[-1].removesuffix("_price")
        matching_level = next(
            (
                float(level)
                for level in SWING_LEVELS
                if level_token(float(level)) == level_token_value
            ),
            None,
        )
        if matching_level is not None:
            deviations.append((matching_level, price))
            if level_near_candles(price, lo, hi):
                extra.append(price)
            else:
                off_chart_levels.append((f"Swing level {matching_level:g}", price, "#ad1457"))
    if selected_deviations:
        swing_lo = _active_swing(events, t_open, "low")
        swing_hi = _active_swing(events, t_open, "high")
        if swing_lo is None or swing_hi is None:
            swing_lo = (
                _finite_at(features, "last_swing_low", t_open) if features is not None else None
            )
            swing_hi = (
                _finite_at(features, "last_swing_high", t_open) if features is not None else None
            )
        if swing_lo is not None and swing_hi is not None and swing_hi > swing_lo:
            span = swing_hi - swing_lo
            deviations = [
                (k, swing_lo + k * span)
                for k in sorted(selected_deviations)
                if any(np.isclose(k, known) for known in DEVIATION_KS)
            ]
            notes.append(
                "Selected deviation levels are k× swing-range projections, not statistical standard deviation"
            )
            for multiple, price in deviations:
                if level_near_candles(price, lo, hi):
                    extra.append(price)
                else:
                    off_chart_levels.append(
                        (f"Selected range projection {multiple:g}x", price, "#607d8b")
                    )

    y0, y1 = chart_ylim(lo, hi, extra)
    # A target with no candle still paints a band, clipped to the candle scale.
    red = _clip_band(metrics.entry_price, metrics.sl_price, y0, y1) if show_sl_tp else None
    green = _clip_band(metrics.entry_price, metrics.tp_price, y0, y1) if show_sl_tp else None
    if ema_exit and show_sl_tp:
        notes.append("EMA-21 management selected; no fixed TP level was set")
    elif show_sl_tp and metrics.tp_price is not None and not tp_on:
        if tp_ref:
            notes.append(tp_label)
        else:
            rr = open_row.get("rr_ratio")
            rr_txt = f" ({float(rr):.2f}R)" if rr is not None and pd.notna(rr) else ""
            notes.append(f"TP {metrics.tp_price:.2f}{rr_txt}")
    if show_sl_tp and metrics.sl_price is not None and not sl_on:
        if sl_ref:
            notes.append(sl_label)
        else:
            notes.append(f"SL {metrics.sl_price:.2f}")

    manip_spans: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    manip_ends: list[pd.Timestamp] = []
    distribution_spans: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    if features is not None and not features.empty:
        manip_spans, manip_ends, distribution_spans, context = _manipulation_marks(
            features,
            window,
            t_open,
            t_close,
            metrics.direction,
            open_row,
            entry_idea_plot_config,
        )
        segs.extend(context)
        extra.extend(seg.price for seg in context)
        y0, y1 = chart_ylim(lo, hi, extra)
        red = _clip_band(metrics.entry_price, metrics.sl_price, y0, y1) if show_sl_tp else None
        green = _clip_band(metrics.entry_price, metrics.tp_price, y0, y1) if show_sl_tp else None

    return OrderLevels(
        ylim=(y0, y1),
        t_open=t_open,
        t_close=t_close,
        entry=metrics.entry_price,
        direction=metrics.direction,
        exit_price=metrics.exit_price,
        red=red,
        green=green,
        segs=segs,
        deviations=deviations,
        notes=notes,
        offset=offset,
        manip_spans=manip_spans,
        manip_ends=manip_ends,
        distribution_spans=distribution_spans,
        off_chart_levels=off_chart_levels,
        zones=zones,
    )


def _clip_band(
    entry: float, other: float | None, y0: float, y1: float
) -> tuple[float, float] | None:
    if other is None:
        return None
    a, b = (entry, other) if entry <= other else (other, entry)
    a = max(a, y0)
    b = min(b, y1)
    if b <= a:
        return None
    return a, b


def draw_order_levels_mpl(
    ax: Any, levels: OrderLevels, stop_updates: pd.DataFrame | None = None
) -> None:
    """Light SL/TP fills, the entry dash, candle marks, and offset arrows."""
    updates = pd.DataFrame() if stop_updates is None else stop_updates.copy()
    if not updates.empty:
        updates = updates.loc[updates["type"].eq("sl_update")].copy()
        time_column = "effective_time" if "effective_time" in updates.columns else "time"
        updates[time_column] = pd.to_datetime(updates[time_column], errors="coerce")
        updates = updates.dropna(subset=[time_column, "price"]).sort_values(time_column)
    labeled_span = False
    for t0, t1 in levels.manip_spans:
        ax.axvspan(
            t0,
            t1,
            color="#7e57c2",
            alpha=0.12,
            linewidth=0,
            zorder=0,
            label="PO3 manipulation phase" if not labeled_span else None,
        )
        labeled_span = True
    labeled_distribution = False
    for t0, t1 in levels.distribution_spans:
        ax.axvspan(
            t0,
            t1,
            color="#26a69a",
            alpha=0.10,
            linewidth=0,
            zorder=0,
            label="PO3 distribution phase" if not labeled_distribution else None,
        )
        labeled_distribution = True
    labeled_end = False
    for ts in levels.manip_ends:
        ax.axvline(
            ts,
            color="#4527a0",
            linewidth=1.0,
            linestyle="-.",
            zorder=2,
            label="manipulation end" if not labeled_end else None,
        )
        labeled_end = True
    if levels.red is not None:
        initial_stop_end = (
            pd.Timestamp(updates.iloc[0][time_column]) if not updates.empty else levels.t_close
        )
        ax.fill_between(
            [levels.t_open, initial_stop_end],
            levels.red[0],
            levels.red[1],
            color=_RED,
            alpha=0.12,
            linewidth=0,
            zorder=0,
        )
    if levels.green is not None:
        ax.fill_between(
            [levels.t_open, levels.t_close],
            levels.green[0],
            levels.green[1],
            color=_GREEN,
            alpha=0.12,
            linewidth=0,
            zorder=0,
        )
    ax.plot(
        [levels.t_open, levels.t_close],
        [levels.entry, levels.entry],
        color=_ENTRY_LINE,
        linewidth=1.0,
        linestyle="--",
        zorder=3,
    )
    seen: set[str] = set()
    labeled_retracement = False
    for seg in levels.segs:
        segment_end = seg.t1
        if not updates.empty and seg.label.startswith("Stop loss"):
            segment_end = pd.Timestamp(updates.iloc[0][time_column])
        ax.plot(
            [seg.t0, segment_end],
            [seg.price, seg.price],
            color=seg.color,
            linewidth=1.0,
            linestyle=seg.linestyle,
            label=(
                "Swing Fibonacci / SD levels"
                if seg.label.startswith("Fib/SD:") and not labeled_retracement
                else seg.label
                if not seg.label.startswith("Fib/SD:") and seg.label not in seen
                else None
            ),
            zorder=3,
        )
        if seg.label.startswith("Fib/SD:"):
            ax.annotate(
                seg.label.removeprefix("Fib/SD: "),
                xy=(segment_end, seg.price),
                xytext=(2, 0),
                textcoords="offset points",
                fontsize=6,
                color=seg.color,
                va="center",
            )
            labeled_retracement = True
        seen.add(seg.label)
        if seg.mark is not None:
            ax.scatter([seg.mark], [seg.price], s=18, color=seg.color, zorder=4, marker="o")
    seen_zones: set[str] = set()
    labeled_zone_midpoint = False
    for zone in levels.zones:
        ax.fill_between(
            [zone.t0, zone.t1],
            zone.low,
            zone.high,
            color=zone.color,
            alpha=0.12,
            linewidth=0,
            label=zone.label if zone.label not in seen_zones else None,
            zorder=1,
        )
        ax.plot(
            [zone.t0, zone.t1],
            [zone.midpoint, zone.midpoint],
            color=zone.color,
            linewidth=0.8,
            linestyle="--",
            alpha=0.8,
            label="Zone midpoint" if not labeled_zone_midpoint else None,
            zorder=2,
        )
        labeled_zone_midpoint = True
        seen_zones.add(zone.label)
    for update_i, (_, update) in enumerate(updates.iterrows()):
        start = pd.Timestamp(update[time_column])
        end = (
            pd.Timestamp(updates.iloc[update_i + 1][time_column])
            if update_i + 1 < len(updates)
            else levels.t_close
        )
        price = float(update["price"])
        ax.plot(
            [start, end],
            [price, price],
            color="#6a1b9a",
            linewidth=1.4,
            linestyle="-.",
            zorder=5,
            label="Active stop after partial" if update_i == 0 else None,
        )
        ax.scatter(
            [start],
            [price],
            marker="D",
            s=24,
            color="#6a1b9a",
            zorder=8,
            label="Stop update" if update_i == 0 else None,
        )
    labeled_sd = False
    for k, price in levels.deviations:
        ax.plot(
            [levels.t_open, levels.t_close],
            [price, price],
            color="#90a4ae",
            linewidth=0.6,
            linestyle=":",
            label=("Selected range projection (not statistical SD)" if not labeled_sd else None),
            zorder=1,
        )
        labeled_sd = True
        ax.annotate(
            f"{k:g}x",
            xy=(levels.t_close, price),
            xytext=(2, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=7,
            color="#607d8b",
        )
    _arrow(
        ax, levels.t_open, levels.entry, levels.direction == 1, "#00cc00", levels.offset, "Entry"
    )
    exit_up = levels.direction != 1
    _arrow(ax, levels.t_close, levels.exit_price, exit_up, "#ff0000", levels.offset, "Exit")
    ax.set_ylim(*levels.ylim)
    y0, y1 = levels.ylim
    for label, price, color in levels.off_chart_levels:
        edge = y0 if price < y0 else y1
        marker = "v" if price < y0 else "^"
        ax.scatter(
            [levels.t_close], [edge], marker=marker, s=35, color=color, zorder=7, clip_on=False
        )
        ax.annotate(
            f"{label}: {price:.2f} (outside view)",
            xy=(levels.t_close, edge),
            xytext=(-8, 8 if edge == y1 else -14),
            textcoords="offset points",
            ha="right",
            va="center",
            fontsize=7,
            color=color,
            clip_on=False,
        )


def _arrow(
    ax: Any,
    when: pd.Timestamp,
    price: float,
    point_up: bool,
    color: str,
    offset: float,
    label: str,
) -> None:
    """Triangle whose tip sits on ``price``, a little off the candle."""
    text_y = price - offset if point_up else price + offset
    ax.annotate(
        "",
        xy=(when, price),
        xytext=(when, text_y),
        arrowprops={"arrowstyle": "-|>", "color": color, "mutation_scale": 12, "lw": 1.2},
        zorder=5,
    )
    ax.scatter([], [], marker="^" if point_up else "v", c=color, s=40, label=label)


def draw_order_levels_plotly(fig: Any, levels: OrderLevels) -> None:
    """Plotly twin of :func:`draw_order_levels_mpl`."""
    import plotly.graph_objects as go

    for t0, t1 in levels.manip_spans:
        fig.add_vrect(
            x0=t0,
            x1=t1,
            fillcolor="#7e57c2",
            opacity=0.12,
            line_width=0,
            row=1,
            col=1,
        )
    for t0, t1 in levels.distribution_spans:
        fig.add_vrect(
            x0=t0,
            x1=t1,
            fillcolor="#26a69a",
            opacity=0.10,
            line_width=0,
            row=1,
            col=1,
        )
    for ts in levels.manip_ends:
        fig.add_vline(
            x=ts,
            line_color="#4527a0",
            line_width=1,
            line_dash="dash",
            row=1,
            col=1,
        )

    def _band(band: tuple[float, float] | None, color: str) -> None:
        if band is None:
            return
        fig.add_shape(
            type="rect",
            x0=levels.t_open,
            x1=levels.t_close,
            y0=band[0],
            y1=band[1],
            fillcolor=color,
            opacity=1,
            line_width=0,
            row=1,
            col=1,
        )

    _band(levels.red, "rgba(229,57,53,0.12)")
    _band(levels.green, "rgba(46,125,50,0.12)")
    fig.add_trace(
        go.Scatter(
            x=[levels.t_open, levels.t_close],
            y=[levels.entry, levels.entry],
            mode="lines",
            name="Entry price",
            line=dict(color=_ENTRY_LINE, width=1, dash="dash"),
        ),
        row=1,
        col=1,
    )
    labeled_retracement = False
    for seg in levels.segs:
        fig.add_trace(
            go.Scatter(
                x=[seg.t0, seg.t1],
                y=[seg.price, seg.price],
                mode="lines",
                name=(
                    "Swing Fibonacci / SD levels" if seg.label.startswith("Fib/SD:") else seg.label
                ),
                legendgroup=(
                    "Swing Fibonacci / SD levels" if seg.label.startswith("Fib/SD:") else seg.label
                ),
                showlegend=not seg.label.startswith("Fib/SD:") or not labeled_retracement,
                line=dict(
                    color=seg.color, width=1, dash="dash" if seg.linestyle == "--" else "dot"
                ),
                hovertemplate=f"{seg.label}<br>Price: %{{y:.2f}}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        if seg.label.startswith("Fib/SD:"):
            labeled_retracement = True
        if seg.mark is not None:
            fig.add_trace(
                go.Scatter(
                    x=[seg.mark],
                    y=[seg.price],
                    mode="markers",
                    name=seg.label,
                    showlegend=False,
                    marker=dict(size=7, color=seg.color, symbol="circle"),
                ),
                row=1,
                col=1,
            )
    seen_zones: set[str] = set()
    labeled_zone_midpoint = False
    for zone in levels.zones:
        fig.add_trace(
            go.Scatter(
                x=[zone.t0, zone.t1, zone.t1, zone.t0],
                y=[zone.low, zone.low, zone.high, zone.high],
                fill="toself",
                fillcolor=zone.color,
                opacity=0.12,
                mode="lines",
                line=dict(width=0, color=zone.color),
                name=zone.label,
                legendgroup=zone.label,
                showlegend=zone.label not in seen_zones,
                hovertemplate=f"{zone.label}: %{{y:.2f}}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=[zone.t0, zone.t1],
                y=[zone.midpoint, zone.midpoint],
                mode="lines",
                name="Zone midpoint",
                legendgroup="Zone midpoint",
                showlegend=not labeled_zone_midpoint,
                line=dict(color=zone.color, width=1, dash="dash"),
                hovertemplate=f"{zone.label} midpoint: %{{y:.2f}}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        labeled_zone_midpoint = True
        seen_zones.add(zone.label)
    for k, price in levels.deviations:
        fig.add_trace(
            go.Scatter(
                x=[levels.t_open, levels.t_close],
                y=[price, price],
                mode="lines",
                name=f"Range projection {k:g}x (not statistical SD)",
                line=dict(color="#90a4ae", width=1, dash="dot"),
            ),
            row=1,
            col=1,
        )
    entry_up = levels.direction == 1
    fig.add_trace(
        go.Scatter(
            x=[levels.t_open],
            y=[levels.entry - levels.offset if entry_up else levels.entry + levels.offset],
            mode="markers",
            name="Entry",
            marker=dict(
                symbol="triangle-up" if entry_up else "triangle-down",
                size=12,
                color="#00cc00",
            ),
        ),
        row=1,
        col=1,
    )
    exit_up = levels.direction != 1
    fig.add_trace(
        go.Scatter(
            x=[levels.t_close],
            y=[levels.exit_price - levels.offset if exit_up else levels.exit_price + levels.offset],
            mode="markers",
            name="Exit",
            marker=dict(
                symbol="triangle-up" if exit_up else "triangle-down",
                size=12,
                color="#ff0000",
            ),
        ),
        row=1,
        col=1,
    )
    fig.update_yaxes(range=list(levels.ylim), row=1, col=1)
