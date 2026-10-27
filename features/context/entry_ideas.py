"""Named, overlapping entry-idea signals for the shared trading policy.

These are independent context flags, not entry gates. Multiple ideas may be
active on the same bar and the policy remains free to trade or stay flat.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Protocol

import numpy as np
import pandas as pd

_TIMEFRAMES = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
ENTRY_IDEA_NAMES = ("po3", "order_block", "standard_deviation", "fvg_retest")


class _FeatureRowLike(Protocol):
    """Minimal row interface shared by pandas rows and the env's numpy view."""

    def get(self, key: str, default: Any = ...) -> Any: ...

    def __getitem__(self, key: str) -> Any: ...

    def __iter__(self) -> Iterator[str]: ...

    def __contains__(self, key: object) -> bool: ...


_EntryIdeaRow = Mapping[str, Any] | pd.Series | _FeatureRowLike


def _matching_positions(columns: Any, suffix: str) -> list[int]:
    return [
        position
        for position, column in enumerate(columns)
        if str(column) == suffix or str(column).endswith(f"_{suffix}")
    ]


def _positive_any_positions(frame: pd.DataFrame, positions: list[int]) -> pd.Series:
    if not positions:
        return pd.Series(False, index=frame.index)
    values = [
        pd.to_numeric(frame.iloc[:, position], errors="coerce").fillna(0.0).gt(0.0)
        for position in positions
    ]
    if len(values) == 1:
        return values[0]
    return pd.concat(values, axis=1).any(axis=1)


def _positive_any(frame: pd.DataFrame, suffix: str) -> pd.Series:
    return _positive_any_positions(frame, _matching_positions(frame.columns, suffix))


def _po3_direction(frame: pd.DataFrame, side: str) -> pd.Series:
    """Require a distribution armed by an IFVG from the active PO3 leg.

    A sweep or manipulation flag alone is context, never an entry idea. The
    PO3 IFVG state is only armed by a gap confirmation after that setup's
    sweep, and the gap must still be active on the entry bar.
    """
    distribution_sign = 1.0 if side == "long" else -1.0
    active_distribution = _positive_any(frame, "po3_distribution_after_ifvg")
    gap_side = "bull" if side == "long" else "bear"
    active_gap = _positive_any(frame, f"ifvg_{gap_side}_active")
    signals = pd.Series(False, index=frame.index)
    for position, raw_column in enumerate(frame.columns):
        column = str(raw_column)
        if column != "po3_distribution_direction" and not column.endswith(
            "_po3_distribution_direction"
        ):
            continue
        prefix = column.removesuffix("po3_distribution_direction")
        direction = pd.to_numeric(frame.iloc[:, position], errors="coerce")
        active_column = f"{prefix}po3_distribution"
        active_positions = [
            active_position
            for active_position, active_name in enumerate(frame.columns)
            if str(active_name) == active_column
        ]
        active = _positive_any_positions(frame, active_positions)
        if not active_positions:
            active = direction.notna() & direction.ne(0.0)
        signals |= active & (direction * distribution_sign > 0.0)
    return signals & active_distribution & active_gap


def build_entry_idea_features(features: pd.DataFrame) -> pd.DataFrame:
    """Add multi-hot idea flags; do not select or gate the agent's action."""
    ideas = pd.DataFrame(index=features.index)
    ideas["entry_idea_po3_long"] = _po3_direction(features, "long").astype("float64")
    ideas["entry_idea_po3_short"] = _po3_direction(features, "short").astype("float64")
    for side, source_side in (("long", "bull"), ("short", "bear")):
        ideas[f"entry_idea_order_block_{side}"] = _positive_any(
            features, f"ob_{source_side}_retest"
        ).astype("float64")
        ideas[f"entry_idea_fvg_retest_{side}"] = (
            _positive_any(features, f"fvg_retest_{source_side}")
            | _positive_any(features, f"ifvg_retest_{source_side}")
            # A body close through an IFVG is itself the directional reaction
            # signal. The policy must not need a later retest of that zone.
            | _positive_any(features, f"ifvg_{source_side}_confirmed")
        ).astype("float64")
        ideas[f"entry_idea_standard_deviation_{side}"] = _positive_any(
            features, f"standard_deviation_entry_{side}"
        ).astype("float64")
    ideas["entry_idea_long_count"] = ideas[
        [f"entry_idea_{idea}_long" for idea in ENTRY_IDEA_NAMES]
    ].sum(axis=1)
    ideas["entry_idea_short_count"] = ideas[
        [f"entry_idea_{idea}_short" for idea in ENTRY_IDEA_NAMES]
    ].sum(axis=1)
    ideas["entry_idea_overlap_long"] = ideas["entry_idea_long_count"].ge(2).astype("float64")
    ideas["entry_idea_overlap_short"] = ideas["entry_idea_short_count"].ge(2).astype("float64")
    return ideas


def _row_values(row: _EntryIdeaRow, column: str) -> list[Any]:
    if isinstance(row, pd.Series):
        return [
            row.iloc[position] for position, name in enumerate(row.index) if str(name) == column
        ]
    value = row.get(column)
    if value is None:
        return []
    if isinstance(value, pd.Series):
        return value.tolist()
    if isinstance(value, (list, tuple, np.ndarray)):
        return list(value)
    return [value]


def _row_items(row: _EntryIdeaRow) -> list[tuple[str, Any]]:
    if isinstance(row, pd.Series):
        return [(str(name), row.iloc[position]) for position, name in enumerate(row.index)]
    return [(str(name), row[name]) for name in row]


def _row_first_value(row: _EntryIdeaRow, column: str) -> Any:
    for value in _row_values(row, column):
        try:
            if pd.isna(value):
                continue
        except (TypeError, ValueError):
            pass
        return value
    return None


def _row_positive(row: _EntryIdeaRow, column: str) -> bool:
    for value in _row_values(row, column):
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if np.isfinite(number) and number > 0.0:
            return True
    return False


def _timeframe_for_column(column: str) -> str:
    for timeframe in _TIMEFRAMES:
        if column.startswith(f"{timeframe}_"):
            return timeframe
    return "M1"


def _zone_contexts(
    row: _EntryIdeaRow,
    ideas: list[str],
    timeframes: Mapping[str, list[str]],
    side: str,
) -> list[dict[str, Any]]:
    """Save only live, direction-matched zones linked to the active idea."""
    zone_families = {
        "po3": ("fvg", "ifvg"),
        "order_block": ("ob",),
        "standard_deviation": (),
        # Keep both active gap types available to the chart. The plot config
        # decides whether the FVG, IFVG, or both are shown for this idea.
        "fvg_retest": ("fvg", "ifvg"),
    }
    source_side = "bull" if side == "long" else "bear"
    contexts: list[dict[str, Any]] = []
    for idea in ideas:
        if idea == "po3":
            tf_by_code = {
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
            try:
                code = int(float(_row_first_value(row, "po3_ifvg_confirmation_tf_code")))
                low = float(_row_first_value(row, "po3_ifvg_low"))
                high = float(_row_first_value(row, "po3_ifvg_high"))
                confirmation_value = _row_first_value(row, "po3_ifvg_time_ns")
                confirmation_time = None if pd.isna(confirmation_value) else int(confirmation_value)
            except (TypeError, ValueError):
                code, low, high, confirmation_time = 0, np.nan, np.nan, None
            if code in tf_by_code and np.isfinite(low + high) and low <= high:
                try:
                    origin_value = _row_first_value(row, "po3_ifvg_fvg_origin_time_ns")
                    origin_time = None if pd.isna(origin_value) else int(origin_value)
                except (TypeError, ValueError):
                    origin_time = None
                timeframe = tf_by_code[code]
                contexts.extend(
                    [
                        {
                            "idea": idea,
                            "family": "fvg",
                            "timeframe": timeframe,
                            "side": source_side,
                            "low": low,
                            "high": high,
                            "start_time_ns": origin_time,
                        },
                        {
                            "idea": idea,
                            "family": "ifvg",
                            "timeframe": timeframe,
                            "side": source_side,
                            "low": low,
                            "high": high,
                            "start_time_ns": confirmation_time,
                        },
                    ]
                )
                continue
        for timeframe in timeframes.get(idea, ["M1"]):
            tf = str(timeframe).upper()
            for family in zone_families[idea]:
                prefix = "" if tf == "M1" and family in {"ob", "ifvg"} else f"{tf}_"
                stem = f"{family}_{source_side}"
                active = _row_positive(row, f"{prefix}{stem}_active")
                if not active:
                    continue
                lows = _row_values(row, f"{prefix}{stem}_low")
                highs = _row_values(row, f"{prefix}{stem}_high")
                for zone_index in range(max(len(lows), len(highs))):
                    if not lows or not highs:
                        continue
                    try:
                        low_value = float(lows[min(zone_index, len(lows) - 1)])
                        high_value = float(highs[min(zone_index, len(highs) - 1)])
                    except (TypeError, ValueError):
                        continue
                    if not np.isfinite(low_value + high_value) or low_value > high_value:
                        continue
                    contexts.append(
                        {
                            "idea": idea,
                            "family": family,
                            "timeframe": tf,
                            "side": source_side,
                            "low": low_value,
                            "high": high_value,
                        }
                    )
    return contexts


def _po3_timeframes(row: _EntryIdeaRow, side: str) -> set[str]:
    if not any(
        (name == "po3_distribution_after_ifvg" or name.endswith("_po3_distribution_after_ifvg"))
        and _row_positive({name: value}, name)
        for name, value in _row_items(row)
    ):
        return set()
    distribution_sign = 1.0 if side == "long" else -1.0
    timeframes: set[str] = set()
    for name, value in _row_items(row):
        suffix = "po3_distribution_direction"
        if name != suffix and not name.endswith(f"_{suffix}"):
            continue
        try:
            direction = float(value)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(direction) or direction * distribution_sign <= 0.0:
            continue
        timeframes.add(_timeframe_for_column(name))
    gap_suffix = f"ifvg_{'bull' if side == 'long' else 'bear'}_active"
    for name, value in _row_items(row):
        if (name == gap_suffix or name.endswith(f"_{gap_suffix}")) and _row_positive(
            {name: value}, name
        ):
            timeframes.add(_timeframe_for_column(name))
    return timeframes


def entry_idea_context(
    row: _EntryIdeaRow,
    direction: int,
    *,
    include_zones: bool = False,
) -> dict[str, Any]:
    """Return idea names and source timeframes present for the chosen side."""
    side = "long" if int(direction) == 1 else "short" if int(direction) == -1 else ""
    if not side:
        return {"ideas": [], "timeframes": {}, "zones": []}

    source_side = "bull" if side == "long" else "bear"
    source_suffixes = {
        "order_block": (f"ob_{source_side}_retest",),
        "standard_deviation": (f"standard_deviation_entry_{side}",),
        "fvg_retest": (
            f"fvg_retest_{source_side}",
            f"ifvg_retest_{source_side}",
            f"ifvg_{source_side}_confirmed",
        ),
    }
    ideas: list[str] = []
    timeframes: dict[str, list[str]] = {}
    for idea in ENTRY_IDEA_NAMES:
        if not _row_positive(row, f"entry_idea_{idea}_{side}"):
            continue
        ideas.append(idea)
        active_tfs = (
            _po3_timeframes(row, side)
            if idea == "po3"
            else {
                _timeframe_for_column(str(column))
                for suffix in source_suffixes[idea]
                for column, value in _row_items(row)
                if (column == suffix or column.endswith(f"_{suffix}"))
                and _row_positive({column: value}, column)
            }
        )
        if idea == "fvg_retest" and _row_positive(row, f"ifvg_{source_side}_confirmed"):
            tf_by_code = {
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
            try:
                code = int(float(_row_first_value(row, f"ifvg_{source_side}_confirmation_tf_code")))
            except (TypeError, ValueError):
                code = 0
            if code in tf_by_code:
                active_tfs.add(tf_by_code[code])
        timeframes[idea] = sorted(active_tfs) or ["M1"]
    return {
        "ideas": ideas,
        "timeframes": timeframes,
        "zones": _zone_contexts(row, ideas, timeframes, side) if include_zones else [],
    }


__all__ = ["ENTRY_IDEA_NAMES", "build_entry_idea_features", "entry_idea_context"]
