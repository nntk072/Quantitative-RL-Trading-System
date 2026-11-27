"""Feature-derived order-chart zones, separated from position geometry."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .geometry_types import ZoneBand


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
    """Plot only the live, side-matched zones linked to this trade's ideas.

    Args:
        features: Feature values supplied to the operation.
        window: Tabular data used for the window.
        open_row: Tabular data used for the open row.
        order_block_timeframes: Items supplied for the order block timeframes, in input order.
        fvg_timeframes: Items supplied for the fvg timeframes, in input order.
        ifvg_timeframes: Items supplied for the ifvg timeframes, in input order.
        entry_idea_plot_config: Key-value data used for the entry idea plot config.

    Returns:
        Values returned by ``_feature_zones``, in the declared order.
    """

    def parse(raw: Any, default: Any) -> Any:
        """Parse a serialized feature value, falling back on malformed input.

        Args:
            raw: Raw used by the operation described above.
            default: Default used by the operation described above.

        Returns:
            Result of parse a serialized feature value, falling back on malformed input.
        """
        if isinstance(raw, str):
            try:
                return ast.literal_eval(raw)
            except (SyntaxError, ValueError):
                return default
        return raw if raw is not None else default

    def tf_values(raw: Any) -> tuple[str, ...]:
        """Normalize a stored timeframe setting into an ordered tuple.

        Args:
            raw: Raw used by the operation described above.

        Returns:
            Values returned by ``tf_values``, in the declared order.
        """
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
