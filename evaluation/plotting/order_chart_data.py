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
from features.technical.structure import TIMEFRAME_CONFIG, structure_levels
from market_data.transforms.resample import resample
from trading.orders import DEVIATION_KS

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
            "fvg_retest": ("fvg",),
            "ifvg_retest": ("ifvg",),
            "ifvg_unretested": ("ifvg",),
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

                    # A candidate can be triggered a few bars after its setup signal. Preserve
                    # its IFVG on the chart even when the signal bar no longer has an active
                    # entry-idea flag.
    if not selected:
        setup_types = parse(open_row.get("entry_setup_types"), ())
        setup_types = set(setup_types) if isinstance(setup_types, (list, tuple, set)) else set()
        if "fvg_retest" in setup_types:
            direction_value = open_row.get("direction", 0)
            try:
                long_trade = float(direction_value) > 0.0
            except (TypeError, ValueError):
                long_trade = str(direction_value).lower() in {"long", "buy", "1"}
            side = "bull" if long_trade else "bear"
            snapshot = parse(open_row.get("entry_setup_levels"), {})
            origin_time = open_row.get("entry_origin_time")
            if (origin_time is None or pd.isna(origin_time)) and isinstance(features, pd.DataFrame):
                origin_bar_value = open_row.get("entry_origin_bar")
                try:
                    origin_bar = (
                        int(float(origin_bar_value))
                        if origin_bar_value is not None and pd.notna(origin_bar_value)
                        else -1
                    )
                except (TypeError, ValueError, OverflowError):
                    origin_bar = -1
                if 0 <= origin_bar < len(features.index):
                    origin_time = features.index[origin_bar]
            try:
                origin_time_ns = (
                    int(pd.Timestamp(origin_time).value)
                    if origin_time is not None and not pd.isna(origin_time)
                    else None
                )
            except (TypeError, ValueError, OverflowError):
                origin_time_ns = None
            if isinstance(snapshot, Mapping):
                for timeframe in ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1"):
                    prefix = "" if timeframe == "M1" else f"{timeframe}_"
                    low = snapshot.get(f"{prefix}ifvg_{side}_low")
                    high = snapshot.get(f"{prefix}ifvg_{side}_high")
                    if low is not None and high is not None and pd.notna(low) and pd.notna(high):
                        selected.append(
                            {
                                "idea": "fvg_retest",
                                "family": "ifvg",
                                "timeframe": timeframe,
                                "side": side,
                                "low": low,
                                "high": high,
                                "start_time_ns": origin_time_ns,
                            }
                        )
            if not selected:
                low = open_row.get("ifvg_zone_low")
                high = open_row.get("ifvg_zone_high")
                try:
                    if (
                        low is not None
                        and high is not None
                        and np.isfinite(float(low))
                        and np.isfinite(float(high))
                    ):
                        selected.append(
                            {
                                "idea": "fvg_retest",
                                "family": "ifvg",
                                "timeframe": "M1",
                                "side": side,
                                "low": float(low),
                                "high": float(high),
                                "start_time_ns": origin_time_ns,
                            }
                        )
                except (TypeError, ValueError):
                    pass

    labels = {
        "ob": ("Order Block", "#2e7d32"),
        "fvg": ("FVG", "#1976d2"),
        "ifvg": ("IFVG", "#ef6c00"),
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
            "PO3 · "
            if idea == "po3"
            else "FVG/IFVG · "
            if idea == "fvg_retest"
            else "IFVG retest · "
            if idea == "ifvg_retest"
            else "IFVG unretested · "
            if idea == "ifvg_unretested"
            else f"{idea.replace('_', ' ').upper()} · "
            if idea
            else ""
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
    bars: pd.DataFrame | None = None,
) -> list[LevelSeg]:
    """Draw selected MTF swings from their actual source wick candles.

    Aligned feature values only say when an MTF level became available. They
    do not identify the pivot candle, so using the first visible feature row as
    the line origin makes levels appear to float in space. Rebuild the small
    structure trace from the supplied M1 bars, map each pivot to the M1 wick
    inside its source timeframe candle, and omit pivots outside the chart.
    """
    ladder = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
    durations = {
        "M3": pd.Timedelta(minutes=3),
        "M5": pd.Timedelta(minutes=5),
        "M10": pd.Timedelta(minutes=10),
        "M15": pd.Timedelta(minutes=15),
        "M30": pd.Timedelta(minutes=30),
        "H1": pd.Timedelta(hours=1),
        "H4": pd.Timedelta(hours=4),
        "D1": pd.Timedelta(days=1),
    }
    rank = {timeframe: index for index, timeframe in enumerate(ladder)}
    aligned = features.reindex(window.index)
    if bars is None or bars.empty or window.empty:
        return []
    segments: list[LevelSeg] = []
    for timeframe in sorted(
        {str(value).upper() for value in timeframes if str(value).upper() != "M1"},
        key=lambda value: rank.get(value, len(rank)),
    ):
        config = TIMEFRAME_CONFIG.get(timeframe)
        duration = durations.get(timeframe)
        if config is None or duration is None:
            continue
        source_bars = resample(bars, timeframe)  # type: ignore[arg-type]
        if source_bars.empty:
            continue
        source_levels = structure_levels(
            source_bars,
            swing_period=int(config["left"]),
            atr_mult=float(config["atr_mult"]),
        )
        prefix = f"{timeframe}_"
        for side, color in (("high", "#8e24aa"), ("low", "#00838f")):
            column = f"{prefix}last_swing_{side}"
            if column not in aligned.columns:
                continue
            source_price_column = f"last_swing_{side}"
            source_time_column = f"last_swing_{side}_time"
            source_prices = pd.to_numeric(
                source_levels[source_price_column], errors="coerce"
            ).to_numpy(dtype=float)
            source_times = source_levels[source_time_column]
            changes = np.flatnonzero(
                source_levels[source_price_column]
                .ne(source_levels[source_price_column].shift())
                .to_numpy()
                & np.isfinite(source_prices)
            )
            values = pd.to_numeric(aligned[column], errors="coerce").to_numpy(dtype=float)
            start: int | None = None
            current: float | None = None
            for idx in range(len(aligned) + 1):
                value = (
                    float(values[idx]) if idx < len(values) and np.isfinite(values[idx]) else None
                )
                if value != current:
                    if start is not None and current is not None:
                        t1 = pd.Timestamp(aligned.index[max(start, idx - 1)])
                        visible_start = pd.Timestamp(aligned.index[start])
                        matching_changes = [
                            source_i
                            for source_i in changes
                            if source_prices[source_i] == current
                            and pd.Timestamp(source_levels.index[source_i]) <= visible_start
                        ]
                        if not matching_changes:
                            start = idx if value is not None else None
                            current = value
                            continue
                        source_i = matching_changes[-1]
                        pivot_time = source_times.iloc[source_i]
                        if pd.isna(pivot_time):
                            start = idx if value is not None else None
                            current = value
                            continue
                        pivot_time = pd.Timestamp(pivot_time)
                        source_bucket = bars.loc[
                            (bars.index >= pivot_time) & (bars.index < pivot_time + duration)
                        ]
                        wick_column = "high" if side == "high" else "low"
                        if source_bucket.empty:
                            start = idx if value is not None else None
                            current = value
                            continue
                        wick_values = pd.to_numeric(source_bucket[wick_column], errors="coerce")
                        exact_wicks = source_bucket.loc[
                            np.isclose(
                                wick_values.to_numpy(dtype=float), current, atol=1e-8, rtol=0.0
                            )
                        ]
                        if exact_wicks.empty:
                            start = idx if value is not None else None
                            current = value
                            continue
                        t0 = pd.Timestamp(exact_wicks.index[0])
                        chart_start = pd.Timestamp(window.index[0])
                        chart_end = pd.Timestamp(window.index[-1])
                        if t0 < chart_start or t0 > chart_end or t1 <= t0:
                            start = idx if value is not None else None
                            current = value
                            continue
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
                                    mark=t0,
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
        segs.extend(_feature_swing_segments(features, window, swing_timeframes, lower_swings, bars))
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
