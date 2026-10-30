"""Named, overlapping entry-idea signals for the shared trading policy.

These are independent context flags, not entry gates. Multiple ideas may be
active on the same bar and the policy remains free to trade or stay flat.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Protocol

import numpy as np
import pandas as pd

from decisioning.thesis import THESIS_IDEAS

_TIMEFRAMES = ("M1", "M3", "M5", "M10", "M15", "M30", "H1", "H4", "D1")
_TIMEFRAME_CODES = dict(zip((1, 3, 5, 10, 15, 30, 60, 240, 1440), _TIMEFRAMES))
ENTRY_IDEA_NAMES = THESIS_IDEAS
_TIMEFRAME_RANK = {timeframe: rank for rank, timeframe in enumerate(_TIMEFRAMES)}


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


def _timeframe_signal(frame: pd.DataFrame, suffix: str, timeframe: str) -> pd.Series:
    """Read one timeframe's event without pooling it with the other windows."""
    prefix = "" if timeframe == "M1" else f"{timeframe}_"
    positions = [
        position
        for position, column in enumerate(frame.columns)
        if str(column) == f"{prefix}{suffix}"
    ]
    signal = _positive_any_positions(frame, positions)
    if suffix.startswith("ifvg_") and suffix.endswith("_confirmed"):
        bare_positions = [
            position for position, column in enumerate(frame.columns) if str(column) == suffix
        ]
        if bare_positions:
            code_positions = _matching_positions(
                frame.columns,
                f"{suffix.removesuffix('_confirmed')}_confirmation_tf_code",
            )
            if code_positions:
                expected_code = next(
                    code for code, tf_name in _TIMEFRAME_CODES.items() if tf_name == timeframe
                )
                code_values = pd.to_numeric(
                    frame.iloc[:, code_positions[0]], errors="coerce"
                ).fillna(0.0)
                if expected_code == 1:
                    signal |= _positive_any_positions(frame, bare_positions) & code_values.isin(
                        [0, expected_code]
                    )
                else:
                    signal |= _positive_any_positions(frame, bare_positions) & code_values.eq(
                        expected_code
                    )
            elif timeframe == "M1":
                signal |= _positive_any_positions(frame, bare_positions)
    return signal


def _po3_direction(frame: pd.DataFrame, side: str, timeframe: str | None = None) -> pd.Series:
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
        if timeframe is not None:
            expected = (
                "po3_distribution_direction"
                if timeframe == "M1"
                else f"{timeframe}_po3_distribution_direction"
            )
            if column != expected:
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
    if timeframe is not None:
        distribution_column = (
            "po3_distribution_after_ifvg"
            if timeframe == "M1"
            else f"{timeframe}_po3_distribution_after_ifvg"
        )
        gap_column = (
            f"ifvg_{gap_side}_active"
            if timeframe == "M1"
            else f"{timeframe}_ifvg_{gap_side}_active"
        )
        active_distribution = _positive_any(frame, distribution_column)
        active_gap = _positive_any(frame, gap_column)
    return signals & active_distribution & active_gap


def build_entry_idea_features(features: pd.DataFrame) -> pd.DataFrame:
    """Add multi-hot idea flags; do not select or gate the agent's action."""
    columns: dict[str, pd.Series] = {
        "entry_idea_po3_long": _po3_direction(features, "long").astype("float64"),
        "entry_idea_po3_short": _po3_direction(features, "short").astype("float64"),
    }
    for side, source_side in (("long", "bull"), ("short", "bear")):
        columns[f"entry_idea_order_block_{side}"] = _positive_any(
            features, f"ob_{source_side}_retest"
        ).astype("float64")
        columns[f"entry_idea_fvg_retest_{side}"] = _positive_any(
            features, f"fvg_retest_{source_side}"
        ).astype("float64")
        columns[f"entry_idea_ifvg_retest_{side}"] = _positive_any(
            features, f"ifvg_retest_{source_side}"
        ).astype("float64")
        # A confirmed body close through an IFVG is the distinct unretested
        # reaction idea; it does not require a later zone retest.
        columns[f"entry_idea_ifvg_unretested_{side}"] = _positive_any(
            features, f"ifvg_{source_side}_confirmed"
        ).astype("float64")
        columns[f"entry_idea_standard_deviation_{side}"] = _positive_any(
            features, f"standard_deviation_entry_{side}"
        ).astype("float64")
        for timeframe in _TIMEFRAMES:
            timeframe_ideas = {
                "po3": _po3_direction(features, side, timeframe),
                "order_block": _timeframe_signal(features, f"ob_{source_side}_retest", timeframe),
                "standard_deviation": _timeframe_signal(
                    features, f"standard_deviation_entry_{side}", timeframe
                ),
                "fvg_retest": _timeframe_signal(features, f"fvg_retest_{source_side}", timeframe),
                "ifvg_retest": _timeframe_signal(features, f"ifvg_retest_{source_side}", timeframe),
                "ifvg_unretested": _timeframe_signal(
                    features, f"ifvg_{source_side}_confirmed", timeframe
                ),
            }
            for idea, values in timeframe_ideas.items():
                columns[f"entry_idea_{idea}_{timeframe}_{side}"] = values.astype("float64")
            columns[f"entry_idea_overlap_{timeframe}_{side}"] = (
                pd.concat([values.astype("float64") for values in timeframe_ideas.values()], axis=1)
                .sum(axis=1)
                .ge(2)
                .astype("float64")
            )
    ideas = pd.DataFrame(columns, index=features.index)
    summary = pd.DataFrame(
        {
            "entry_idea_long_count": ideas[
                [f"entry_idea_{idea}_long" for idea in ENTRY_IDEA_NAMES]
            ].sum(axis=1),
            "entry_idea_short_count": ideas[
                [f"entry_idea_{idea}_short" for idea in ENTRY_IDEA_NAMES]
            ].sum(axis=1),
        },
        index=features.index,
    )
    summary["entry_idea_overlap_long"] = summary["entry_idea_long_count"].ge(2).astype("float64")
    summary["entry_idea_overlap_short"] = summary["entry_idea_short_count"].ge(2).astype("float64")
    ideas = pd.concat([ideas, summary], axis=1)
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
        # Keep gap families separate in the trade context so plots can show
        # the exact active FVG or IFVG tied to the selected idea.
        "fvg_retest": ("fvg",),
        "ifvg_retest": ("ifvg",),
        "ifvg_unretested": ("ifvg",),
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
        return {
            "ideas": [],
            "timeframes": {},
            "stop_timeframe_floor": "M1",
            "standard_deviation_timeframes": [],
            "gap_reactions": {},
            "zones": [],
        }

    source_side = "bull" if side == "long" else "bear"
    source_suffixes = {
        "order_block": (f"ob_{source_side}_retest",),
        "standard_deviation": (f"standard_deviation_entry_{side}",),
        "fvg_retest": (f"fvg_retest_{source_side}",),
        "ifvg_retest": (f"ifvg_retest_{source_side}",),
        "ifvg_unretested": (f"ifvg_{source_side}_confirmed",),
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
        if idea == "ifvg_unretested" and _row_positive(row, f"ifvg_{source_side}_confirmed"):
            try:
                code = int(float(_row_first_value(row, f"ifvg_{source_side}_confirmation_tf_code")))
            except (TypeError, ValueError):
                code = 0
            if code in _TIMEFRAME_CODES:
                if code != 1:
                    active_tfs.discard("M1")
                active_tfs.add(_TIMEFRAME_CODES[code])
        timeframes[idea] = sorted(active_tfs) or ["M1"]
    gap_reactions: dict[str, list[str]] = {}
    for label, suffixes in (
        ("FVG", (f"fvg_retest_{source_side}",)),
        ("IFVG", (f"ifvg_retest_{source_side}",)),
    ):
        active_tfs = {
            _timeframe_for_column(str(column))
            for suffix in suffixes
            for column, value in _row_items(row)
            if (column == suffix or column.endswith(f"_{suffix}"))
            and _row_positive({column: value}, column)
        }
        if label == "IFVG" and _row_positive(row, f"ifvg_{source_side}_confirmed"):
            try:
                code = int(float(_row_first_value(row, f"ifvg_{source_side}_confirmation_tf_code")))
            except (TypeError, ValueError):
                code = 0
            if code in _TIMEFRAME_CODES:
                active_tfs.add(_TIMEFRAME_CODES[code])
            elif code == 0:
                active_tfs.add("M1")
        if active_tfs:
            gap_reactions[label] = sorted(active_tfs)
    active_timeframes = [
        timeframe
        for values in timeframes.values()
        for timeframe in values
        if timeframe in _TIMEFRAME_RANK
    ]
    stop_timeframe_floor = (
        max(active_timeframes, key=_TIMEFRAME_RANK.__getitem__) if active_timeframes else "M1"
    )
    standard_deviation_timeframes = sorted(
        timeframes.get("standard_deviation", []), key=_TIMEFRAME_RANK.__getitem__
    )
    return {
        "ideas": ideas,
        "timeframes": timeframes,
        "stop_timeframe_floor": stop_timeframe_floor,
        "standard_deviation_timeframes": standard_deviation_timeframes,
        "gap_reactions": gap_reactions,
        "zones": _zone_contexts(row, ideas, timeframes, side) if include_zones else [],
    }


__all__ = ["ENTRY_IDEA_NAMES", "build_entry_idea_features", "entry_idea_context"]
