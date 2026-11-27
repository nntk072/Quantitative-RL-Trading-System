"""Simulation-specific observation window and timeframe composition."""

from __future__ import annotations

from typing import Any, cast

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


def sanitize_observation_values(values: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """Map invalid feature values to neutral zero before policy inference.

    Args:
        values: Feature array that may contain NaN or infinite values.

    Returns:
        Float32 array with invalid values replaced by zero.
    """
    array = np.asarray(values, dtype=np.float32)
    return cast(
        np.ndarray[Any, Any],
        np.nan_to_num(array, nan=0.0, posinf=0.0, neginf=0.0),
    )


def prepare_observation_feature_channels(
    values: np.ndarray[Any, Any],
    *,
    include_validity: bool,
) -> np.ndarray[Any, Any]:
    """Sanitize feature values and optionally append their finite-value mask.

    Args:
        values: Two-dimensional feature window.
        include_validity: Whether to append one finite-value indicator per feature.

    Returns:
        Sanitized features, optionally concatenated with validity channels.
    """
    array = np.asarray(values, dtype=np.float32)
    if array.ndim != 2:
        raise ValueError("observation feature values must be a two-dimensional array")
    finite_mask = np.isfinite(array)
    validity = finite_mask.astype(np.float32)
    # Same values as sanitize_observation_values (nan/inf -> 0), one mask and no
    # nan_to_num call overhead per observation channel.
    finite_values = np.where(finite_mask, array, np.float32(0.0)).astype(np.float32, copy=False)
    if not include_validity:
        return finite_values
    return cast(np.ndarray[Any, Any], np.concatenate((finite_values, validity), axis=1))


def split_obs_columns(
    names: list[str],
    timeframes: tuple[str, ...] | list[str] = AVAILABLE_OBSERVATION_TIMEFRAMES,
) -> tuple[np.ndarray[Any, Any], dict[str, np.ndarray[Any, Any]]]:
    """Route timeframe-prefixed features to their own model stream.

    Args:
        names: Items supplied for the names, in input order.
        timeframes: Items supplied for the timeframes, in input order.

    Returns:
        Mapping from ``str`` keys to ``np.ndarray[Any, Any]]`` values.
    """
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
    """Index of the first row of each run of constant columns. NaN matches NaN.

    Args:
        block: Block used by the operation described above.

    Returns:
        Array returned by ``run_starts``.
    """
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

    Args:
        index: Position or label identifying the requested item.
        timeframe: Text or path value identifying the timeframe.
        scheduled_closes: Key-value data used for the scheduled closes.
        session_start: Text or path value identifying the session start.

    Returns:
        Array returned by ``timeframe_starts``.
    """
    if len(index) == 0:
        return np.zeros(0, dtype=np.int64)
    source = pd.DataFrame({"open": np.ones(len(index), dtype=np.float32)}, index=index)
    candles = resample(source, timeframe)  # type: ignore[arg-type]
    closes = timeframe_close_times(candles, timeframe, scheduled_closes, session_start)
    starts = index.searchsorted(pd.DatetimeIndex(closes), side="left")
    valid_starts = starts[starts < len(index)]
    return np.asarray(np.unique(valid_starts), dtype=np.int64)


def closed_window_raw(
    block: np.ndarray[Any, Any],
    starts: np.ndarray[Any, Any],
    end: int,
    length: int,
    columns: np.ndarray[Any, Any] | None = None,
) -> np.ndarray[Any, Any]:
    """Raw float32 rows of ``closed_window`` before sanitizing and padding.

    Same rows and shapes as ``closed_window`` uses internally, so that
    ``pad(prepare(closed_window_raw(...)))`` equals ``closed_window(...)``.

    Args:
        block: Feature block to gather from.
        starts: Starts of each closed run.
        end: Decision row.
        length: Window length in runs.
        columns: Selected columns, or None for all.

    Returns:
        Raw values with shape ``(rows, width)`` (or ``(0, 1)`` for a block without columns).
    """
    if block.ndim != 2:
        return np.zeros((0, 1), dtype=np.float32)
    selected_columns = None if columns is None else np.asarray(columns, dtype=np.int64)
    width = int(block.shape[1]) if selected_columns is None else int(selected_columns.size)
    if width == 0:
        return np.zeros((0, 1), dtype=np.float32)
    decision = int(end)
    if decision < 0 or starts.size == 0:
        return np.zeros((0, width), dtype=np.float32)
    visible_end = int(np.searchsorted(starts, decision, side="right"))
    if visible_end == 0:
        return np.zeros((0, width), dtype=np.float32)
    first_visible = max(0, visible_end - int(length))
    visible = starts[first_visible:visible_end]
    rows = np.empty(visible.size, dtype=np.int64)
    rows[:-1] = visible[1:] - 1
    rows[-1] = decision
    # Row gather then column pick is the same values and about twice as fast as np.ix_.
    return np.asarray(
        block[rows] if selected_columns is None else block[rows][:, selected_columns],
        dtype=np.float32,
    )


def prepare_observation_feature_channels_many(
    values_list: list[np.ndarray[Any, Any]],
    *,
    include_validity: bool,
) -> list[np.ndarray[Any, Any]]:
    """``prepare_observation_feature_channels`` for several windows in one pass.

    Sanitizing and the finite mask are elementwise, so they are computed once over
    the concatenated values and split back per window. The result equals calling
    ``prepare_observation_feature_channels`` on each window separately.

    Args:
        values_list: Two-dimensional raw windows.
        include_validity: Whether to append per-feature finite-value channels.

    Returns:
        Prepared windows, one per input, in order.
    """
    arrays = [np.asarray(values, dtype=np.float32) for values in values_list]
    for array in arrays:
        if array.ndim != 2:
            raise ValueError("observation feature values must be a two-dimensional array")
    if not arrays:
        return []
    flat = np.concatenate([array.ravel() for array in arrays])
    finite_mask = np.isfinite(flat)
    clean = np.where(finite_mask, flat, np.float32(0.0)).astype(np.float32, copy=False)
    outputs: list[np.ndarray[Any, Any]] = []
    offset = 0
    for array in arrays:
        size = array.size
        values = clean[offset : offset + size].reshape(array.shape)
        if include_validity:
            validity = finite_mask[offset : offset + size].reshape(array.shape).astype(np.float32)
            outputs.append(np.concatenate((values, validity), axis=1))
        else:
            outputs.append(values)
        offset += size
    return outputs


def closed_window(
    block: np.ndarray[Any, Any],
    starts: np.ndarray[Any, Any],
    end: int,
    length: int,
    columns: np.ndarray[Any, Any] | None = None,
    include_validity: bool = False,
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    """Last ``length`` closed runs at or before ``end``, oldest to newest.

    ``end`` is the decision row and is included. The row kept for the run that
    contains it is ``end`` itself, so a candle that first appears later is absent.
    A block with no columns is shape ``(length, 1)`` of zeros and a zero mask.

    Args:
        block: Block used by the operation described above.
        starts: Starts used by the operation described above.
        end: Numeric value used for the end.
        length: Numeric value used for the length.
        columns: Columns used by the operation described above.
        include_validity: Append per-feature finite-value mask channels.

    Returns:
        Array returned by ``closed_window``.
    """
    if block.ndim != 2:
        empty = np.zeros((0, 1), dtype=np.float32)
        empty = prepare_observation_feature_channels(empty, include_validity=include_validity)
        return pad_observation_window(empty, length)
    selected_columns = None if columns is None else np.asarray(columns, dtype=np.int64)
    width = int(block.shape[1]) if selected_columns is None else int(selected_columns.size)
    if width == 0:
        empty = np.zeros((0, 1), dtype=np.float32)
        empty = prepare_observation_feature_channels(empty, include_validity=include_validity)
        return pad_observation_window(empty, length)
    decision = int(end)
    if decision < 0 or starts.size == 0:
        empty = np.zeros((0, width), dtype=np.float32)
        empty = prepare_observation_feature_channels(empty, include_validity=include_validity)
        return pad_observation_window(empty, length)
    visible_end = int(np.searchsorted(starts, decision, side="right"))
    if visible_end == 0:
        empty = np.zeros((0, width), dtype=np.float32)
        empty = prepare_observation_feature_channels(empty, include_validity=include_validity)
        return pad_observation_window(empty, length)
    first_visible = max(0, visible_end - int(length))
    visible = starts[first_visible:visible_end]
    rows = np.empty(visible.size, dtype=np.int64)
    rows[:-1] = visible[1:] - 1
    rows[-1] = decision
    values_block = (
        block[rows] if selected_columns is None else block[np.ix_(rows, selected_columns)]
    )
    values = prepare_observation_feature_channels(values_block, include_validity=include_validity)
    return pad_observation_window(values, length)
