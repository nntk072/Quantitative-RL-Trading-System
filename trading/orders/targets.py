"""Structural target candidate construction and market-level selection."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from features.context.swing_retracement import SWING_LEVELS, level_token

_PRICE_TOL = 1e-4


def normalize_timeframe(tf: str) -> str:
    """Normalise a time-frame key to the uppercase column prefix used by align_timeframes.

    ``DEFAULT_HTF_WINDOWS`` and ``HTF_BRANCHES`` use lowercase keys (``m5``), but
    ``align_timeframes`` prefixes columns with the TF string from ``_htf_list``
    which is uppercase (``M5``).  Without this normalisation, an ``htf`` tuple
    sourced from ``env._mtf_windows.keys()`` would miss every HTF level column.
    """
    return str(tf).upper()


_TARGET_TIMEFRAMES = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H2", "H4", "D1", "W1")


def _target_timeframe(name: str) -> str:
    """Resolve a structural reference's timeframe, conservatively by source."""
    head = str(name).split("|", 1)[0]
    for timeframe in _TARGET_TIMEFRAMES:
        if head.startswith(f"{timeframe}_"):
            return timeframe
    if head.startswith(("prev_day_", "ctx_prev_day_", "yesterday_")):
        return "D1"
    if head.startswith(("lastweek_", "ctx_prev_week_")):
        return "W1"
    return "M1"


def collapse_levels(
    items: list[tuple[str, float]], *, price_increment: float | None = None
) -> list[tuple[str, float]]:
    """Merge prices within ``1e-4`` and join their names with ``|``."""
    if price_increment is not None and (not np.isfinite(price_increment) or price_increment <= 0.0):
        raise ValueError("price_increment must be finite and positive")
    groups: list[tuple[str, float]] = []
    keys: list[int | float] = []
    for name, price in items:
        px = float(price)
        if not np.isfinite(px):
            continue
        key: int | float = int(np.rint(px / price_increment)) if price_increment is not None else px
        merged = False
        for i, (names, kept) in enumerate(groups):
            same_level = (
                key == keys[i] if price_increment is not None else abs(px - kept) <= _PRICE_TOL
            )
            if same_level:
                parts = names.split("|")
                if name not in parts:
                    groups[i] = (names + "|" + name, kept)
                merged = True
                break
        if not merged:
            groups.append((name, px))
            keys.append(key)
    return groups


def target_menu(
    *,
    direction: int,
    entry_price: float,
    row: Any,
    stop_dist: float,
    max_tp_distance: float,
    rr_bounds: tuple[float, float] | None = None,
    htf: tuple[str, ...] = ("M5", "M15", "H1"),
    front_run_pts: float = 0.0,
    price_increment: float | None = None,
    source_prices: dict[str, float] | None = None,
    min_timeframe: str | None = None,
) -> list[tuple[str, float, float]]:
    if not np.isfinite(front_run_pts) or front_run_pts < 0.0:
        raise ValueError("front_run_pts must be finite and nonnegative")
    if price_increment is not None and (not np.isfinite(price_increment) or price_increment <= 0.0):
        raise ValueError("price_increment must be finite and positive")
    if direction == 1:
        names = [
            "last_swing_high",
            "asian_high",
            "london_high",
            "prev_day_high",
            "ctx_prev_week_high",
            "sweep_high_level",
        ]
        gap_suffixes = ("ifvg_bear_low", "fvg_bear_low")
        swing_name = "last_swing_high"
        ob_target_stem = "ob_bear_high"
    else:
        names = [
            "last_swing_low",
            "asian_low",
            "london_low",
            "prev_day_low",
            "ctx_prev_week_low",
            "sweep_low_level",
        ]
        gap_suffixes = ("ifvg_bull_high", "fvg_bull_high")
        swing_name = "last_swing_low"
        ob_target_stem = "ob_bull_low"
    raw: list[tuple[str, float]] = []
    for name in names:
        level = finite_level(row, name)
        if level is not None:
            raw.append((name, level))
    for tf in htf:
        tf_up = normalize_timeframe(str(tf))
        level = finite_level(row, f"{tf_up}_{swing_name}")
        if level is not None:
            raw.append((f"{tf_up}_{swing_name}", level))
    row_columns = getattr(row, "index", ())
    for column in row_columns:
        column_name = str(column)
        if column_name == ob_target_stem or column_name.endswith(f"_{ob_target_stem}"):
            active_name = column_name.removesuffix("_low").removesuffix("_high") + "_active"
            if finite_level(row, active_name) == 1.0:
                level = finite_level(row, column_name)
                if level is not None:
                    raw.append((column_name, level))
    raw.extend(suffixed_levels(row, gap_suffixes))
    # TP extensions belong to the confirmed swing leg and are available to
    # every entry idea. The stop menu keeps its separate, nearer-level cap.
    raw.extend(deviation_candidates(row, allow_extreme_extension=True))
    if source_prices is not None:
        source_prices.update((name, float(price)) for name, price in raw)
    # A known confirmation after the decision is never eligible. The pivot
    # origin (`*_time`) is not a confirmation time and is not used here.
    decision_at = getattr(row, "name", None)
    if not isinstance(decision_at, pd.Timestamp):
        decision_at = None
    available: list[tuple[str, float]] = []
    minimum_rank = (
        _TARGET_TIMEFRAMES.index(normalize_timeframe(min_timeframe))
        if min_timeframe is not None
        else 0
    )
    for name, level in raw:
        if _TARGET_TIMEFRAMES.index(_target_timeframe(name)) < minimum_rank:
            continue
        confirmed_at = row.get(f"{name}_confirmed_at") if hasattr(row, "get") else None
        if confirmed_at is not None and not pd.isna(confirmed_at):
            if decision_at is None:
                continue  # explicit availability requires an actual decision clock
            try:
                if pd.Timestamp(confirmed_at) > decision_at:
                    continue
            except (TypeError, ValueError):
                continue  # fail closed on invalid or timezone-incompatible metadata
        available.append((name, level))
    room = float(max_tp_distance) if max_tp_distance is not None else float("nan")
    ranked: list[tuple[str, float, float, bool]] = []
    rr_lo, rr_hi = (
        (float(rr_bounds[0]), float(rr_bounds[1]))
        if rr_bounds is not None
        else (float("-inf"), float("inf"))
    )
    for name, level in collapse_levels(available):
        if front_run_pts:
            level = float(level) - direction * float(front_run_pts)
        if price_increment is not None:
            units = level / price_increment
            if direction == 1:
                level = float(np.floor(units + 1e-10) * price_increment)
            else:
                level = float(np.ceil(units - 1e-10) * price_increment)
        if direction == 1 and level <= entry_price:
            continue
        if direction == -1 and level >= entry_price:
            continue
        dist = abs(level - entry_price)
        if dist + 1e-12 < stop_dist:
            continue
        if np.isfinite(room) and dist > room + 1e-9:
            continue
        # strategy.risk.rr_range is the promised reward-to-risk window. It was
        # read into TradingEnv.rr_ratio_range and then never applied to the
        # menu, so ~44% of trades settled outside [1.5, 5.0].
        implied = dist / stop_dist if stop_dist > 1e-12 else float("inf")
        ranked.append((name, float(level), dist, rr_lo - 1e-9 <= implied <= rr_hi + 1e-9))
    # Enforce the window whenever the bar offers at least one level inside it.
    # Falling back when nothing qualifies keeps the menu usable instead of
    # rejecting a setup purely because no structural level happened to land in
    # the window — a stop that exists is still better than no trade at all.
    legal = [item for item in ranked if item[3]]
    chosen = legal or ranked
    menu = [(name, level, dist) for name, level, dist, _in_range in chosen]
    if price_increment is not None or front_run_pts:
        # Different original references can map to the same executable tick.
        deduped = collapse_levels([(name, level) for name, level, _ in menu])
        menu = [(name, px, abs(px - entry_price)) for name, px in deduped]
    menu.sort(key=lambda item: item[2])
    return menu


def deviation_candidates(
    row: Any, *, allow_extreme_extension: bool = False
) -> list[tuple[str, float]]:
    """Use extensions of already-created swing legs as TP levels.

    Prices are precomputed from the latest *confirmed* swing source on each
    timeframe. Recomputing from current bars or session ranges here could make
    target choices disagree with the feature/plot source.
    """
    columns = getattr(row, "index", ())
    levels_by_name = {
        f"standard_deviation_level_{level_token(level)}_price": level for level in SWING_LEVELS
    }
    minimum_level = -8.0 if allow_extreme_extension else -4.0
    out: list[tuple[str, float]] = []
    for raw_column in columns:
        column = str(raw_column)
        if not any(column == name or column.endswith(f"_{name}") for name in levels_by_name):
            continue
        level = finite_level(row, column)
        configured_level = next(
            (
                value
                for name, value in levels_by_name.items()
                if column == name or column.endswith(f"_{name}")
            ),
            None,
        )
        if level is not None and configured_level is not None and configured_level >= minimum_level:
            out.append((column, level))
    return out


def suffixed_levels(row: Any, suffixes: tuple[str, ...]) -> list[tuple[str, float]]:
    index = getattr(row, "index", ())
    found: list[tuple[str, float]] = []
    for col in index:
        text = str(col)
        if any(text == suffix or text.endswith("_" + suffix) for suffix in suffixes):
            level = finite_level(row, text)
            if level is not None:
                found.append((text, level))
    return found


def finite_level(row: Any, name: str) -> float | None:
    index = getattr(row, "index", None)
    if index is not None and name not in index:
        return None
    try:
        value = float(row.get(name, np.nan))
    except (TypeError, ValueError):
        return None
    if not np.isfinite(value):
        return None
    return value


__all__ = [
    "collapse_levels",
    "deviation_candidates",
    "finite_level",
    "normalize_timeframe",
    "suffixed_levels",
    "target_menu",
]
