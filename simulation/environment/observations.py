"""Simulation-specific observation window and timeframe composition."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from decisioning.observations import pad_observation_window
from market_data.transforms.align import timeframe_close_times
from market_data.transforms.resample import resample

AVAILABLE_OBSERVATION_TIMEFRAMES: tuple[str, ...] = (
    "M1",
    "M3",
    "M5",
    "M10",
    "M15",
    "M30",
    "H1",
    "H4",
    "D1",
)
HTF_BRANCHES: tuple[tuple[str, str, str], ...] = tuple(
    (timeframe.lower(), f"{timeframe}_", f"seq_{timeframe.lower()}")
    for timeframe in AVAILABLE_OBSERVATION_TIMEFRAMES
    if timeframe != "M1"
)
DEFAULT_MTF_TIMEFRAMES: tuple[str, ...] = AVAILABLE_OBSERVATION_TIMEFRAMES
DEFAULT_HTF_WINDOWS: dict[str, int] = {
    "m3": 20,
    "m5": 24,
    "m10": 12,
    "m15": 16,
    "m30": 8,
    "h1": 12,
    "h4": 6,
    "d1": 5,
}


def split_obs_columns(
    names: list[str],
    timeframes: tuple[str, ...] | list[str] = AVAILABLE_OBSERVATION_TIMEFRAMES,
) -> tuple[np.ndarray[Any, Any], dict[str, np.ndarray[Any, Any]]]:
    """Route timeframe-prefixed features to their own model stream."""
    m1: list[int] = []
    configured = {str(timeframe).upper() for timeframe in timeframes}
    branches = tuple(branch for branch in HTF_BRANCHES if branch[0].upper() in configured)
    grouped: dict[str, list[int]] = {key: [] for key, _, _ in HTF_BRANCHES}
    prefixes = {key: prefix for key, prefix, _ in branches}
    all_prefixes = {prefix: key for key, prefix, _ in HTF_BRANCHES}
    for i, name in enumerate(names):
        text = str(name)
        branch = next((key for key, prefix in prefixes.items() if text.startswith(prefix)), None)
        if branch is None:
            if not any(text.startswith(prefix) for prefix in all_prefixes):
                m1.append(i)
        else:
            grouped[branch].append(i)
    return (
        np.asarray(m1, dtype=np.int64),
        {key: np.asarray(idx, dtype=np.int64) for key, idx in grouped.items()},
    )


def run_starts(block: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """Index of the first row of each run of constant columns. NaN matches NaN."""
    rows = int(block.shape[0]) if block.ndim == 2 else 0
    if rows == 0 or int(block.shape[1]) == 0:
        return np.zeros(0, dtype=np.int64)
    changed = np.ones(rows, dtype=bool)
    if rows > 1:
        prev = block[:-1]
        curr = block[1:]
        both_nan = np.isnan(prev) & np.isnan(curr)
        changed[1:] = np.any((prev != curr) & ~both_nan, axis=1)
    return np.flatnonzero(changed).astype(np.int64)


def timeframe_starts(
    index: pd.DatetimeIndex,
    timeframe: str,
    scheduled_closes: dict[str, str] | None = None,
    session_start: str = "16:30",
) -> np.ndarray[Any, Any]:
    """Map completed timeframe candles to their first visible M1 decision row.

    Boundaries come from resampled M1 timestamps rather than feature changes,
    so identical consecutive feature rows remain separate candle observations.
    """
    if len(index) == 0:
        return np.zeros(0, dtype=np.int64)
    source = pd.DataFrame({"open": np.ones(len(index), dtype=np.float32)}, index=index)
    candles = resample(source, timeframe)  # type: ignore[arg-type]
    closes = timeframe_close_times(candles, timeframe, scheduled_closes, session_start)
    starts = index.searchsorted(pd.DatetimeIndex(closes), side="left")
    valid_starts = starts[starts < len(index)]
    return np.asarray(np.unique(valid_starts), dtype=np.int64)


def closed_window(
    block: np.ndarray[Any, Any],
    starts: np.ndarray[Any, Any],
    end: int,
    length: int,
    columns: np.ndarray[Any, Any] | None = None,
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    """Last ``length`` closed runs at or before ``end``, oldest to newest.

    ``end`` is the decision row and is included. The row kept for the run that
    contains it is ``end`` itself, so a candle that first appears later is absent.
    A block with no columns is shape ``(length, 1)`` of zeros and a zero mask.
    """
    if block.ndim != 2:
        empty = np.zeros((0, 1), dtype=np.float32)
        return pad_observation_window(empty, length)
    selected_columns = None if columns is None else np.asarray(columns, dtype=np.int64)
    width = int(block.shape[1]) if selected_columns is None else int(selected_columns.size)
    if width == 0:
        empty = np.zeros((0, 1), dtype=np.float32)
        return pad_observation_window(empty, length)
    decision = int(end)
    if decision < 0 or starts.size == 0:
        return pad_observation_window(np.zeros((0, width), dtype=np.float32), length)
    visible_end = int(np.searchsorted(starts, decision, side="right"))
    if visible_end == 0:
        return pad_observation_window(np.zeros((0, width), dtype=np.float32), length)
    first_visible = max(0, visible_end - int(length))
    visible = starts[first_visible:visible_end]
    rows = np.empty(visible.size, dtype=np.int64)
    rows[:-1] = visible[1:] - 1
    rows[-1] = decision
    values_block = (
        block[rows] if selected_columns is None else block[np.ix_(rows, selected_columns)]
    )
    values = np.nan_to_num(np.asarray(values_block, dtype=np.float32), nan=0.0)
    return pad_observation_window(values, length)
