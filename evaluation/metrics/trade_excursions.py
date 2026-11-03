"""Tick-price excursion bounds for a completed trade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class TradeExcursionBounds:
    """Executable-side MFE/MAE bounds when endpoint tick order is unresolved."""

    mfe_price_lower: float
    mfe_price_upper: float
    mae_price_lower: float
    mae_price_upper: float
    inclusive_tick_rows: int
    strict_interior_tick_rows: int
    entry_timestamp_tie_rows: int
    exit_timestamp_tie_rows: int


def trade_excursion_bounds(
    timestamps_ns: NDArray[np.integer[Any]],
    liquidation_prices: NDArray[np.floating[Any]],
    *,
    entry_time_ns: int,
    exit_time_ns: int,
    direction: int,
    entry_price: float,
    entry_liquidation_price: float,
    exit_liquidation_price: float,
) -> TradeExcursionBounds:
    """Measure price excursions and bound unresolved entry/exit timestamp ties.

    The lower path uses only strictly interior tick rows plus the recorded
    entry/exit liquidation-side prices. The upper path also includes every
    source row sharing either endpoint timestamp. This makes the result robust
    to unknown sub-timestamp ordering without inventing an order for tied rows.

    Args:
        timestamps_ns: Sorted UTC nanosecond timestamps from the execution quote
            stream. Equal values are retained.
        liquidation_prices: Executable-side prices aligned to ``timestamps_ns``
            (bid for long positions, ask for short positions).
        entry_time_ns: Recorded opening fill timestamp in UTC nanoseconds.
        exit_time_ns: Recorded final closing fill timestamp in UTC nanoseconds.
        direction: ``1`` for long or ``-1`` for short.
        entry_price: Recorded opening fill price.
        entry_liquidation_price: Liquidation-side quote paired with the opening
            fill timestamp.
        exit_liquidation_price: Liquidation-side quote paired with the final
            closing fill timestamp.

    Returns:
        A lower and upper MFE/MAE bound in price units, with tie-row counts.

    Raises:
        ValueError: If the direction, prices, timestamps, or array alignment is
            invalid, or no usable quote exists strictly inside the position.
    """
    timestamps = np.asarray(timestamps_ns)
    prices = np.asarray(liquidation_prices, dtype=np.float64)
    if timestamps.ndim != 1 or prices.ndim != 1 or timestamps.shape != prices.shape:
        raise ValueError("timestamps_ns and liquidation_prices must be aligned 1D arrays")
    if timestamps.dtype.kind not in "iu":
        raise ValueError("timestamps_ns must contain integer UTC nanoseconds")
    if timestamps.size and np.any(np.diff(timestamps.astype(np.int64, copy=False)) < 0):
        raise ValueError("timestamps_ns must be sorted in nondecreasing order")
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")
    if entry_time_ns > exit_time_ns:
        raise ValueError("entry_time_ns cannot be after exit_time_ns")

    endpoints = np.asarray(
        [entry_price, entry_liquidation_price, exit_liquidation_price], dtype=np.float64
    )
    if not np.isfinite(endpoints).all() or np.any(endpoints <= 0.0):
        raise ValueError("entry and liquidation prices must be finite and positive")

    timestamp_values = timestamps.astype(np.int64, copy=False)
    first_inclusive = int(np.searchsorted(timestamp_values, entry_time_ns, side="left"))
    after_inclusive = int(np.searchsorted(timestamp_values, exit_time_ns, side="right"))
    first_interior = int(np.searchsorted(timestamp_values, entry_time_ns, side="right"))
    after_interior = int(np.searchsorted(timestamp_values, exit_time_ns, side="left"))

    inclusive = prices[first_inclusive:after_inclusive]
    interior = prices[first_interior:after_interior]
    usable_interior = interior[np.isfinite(interior) & (interior > 0.0)]
    usable_inclusive = inclusive[np.isfinite(inclusive) & (inclusive > 0.0)]

    lower_path = np.concatenate(
        (
            np.asarray([entry_liquidation_price, exit_liquidation_price], dtype=np.float64),
            usable_interior,
        )
    )
    upper_path = np.concatenate(
        (
            np.asarray([entry_liquidation_price, exit_liquidation_price], dtype=np.float64),
            usable_inclusive,
        )
    )

    def excursions(path: NDArray[np.float64]) -> tuple[float, float]:
        signed_move = direction * (path - entry_price)
        return (
            max(0.0, float(np.max(signed_move))),
            max(0.0, float(-np.min(signed_move))),
        )

    mfe_lower, mae_lower = excursions(lower_path)
    mfe_upper, mae_upper = excursions(upper_path)
    return TradeExcursionBounds(
        mfe_price_lower=mfe_lower,
        mfe_price_upper=mfe_upper,
        mae_price_lower=mae_lower,
        mae_price_upper=mae_upper,
        inclusive_tick_rows=int(len(inclusive)),
        strict_interior_tick_rows=int(len(interior)),
        entry_timestamp_tie_rows=int(
            np.searchsorted(timestamp_values, entry_time_ns, side="right")
            - np.searchsorted(timestamp_values, entry_time_ns, side="left")
        ),
        exit_timestamp_tie_rows=int(
            np.searchsorted(timestamp_values, exit_time_ns, side="right")
            - np.searchsorted(timestamp_values, exit_time_ns, side="left")
        ),
    )
