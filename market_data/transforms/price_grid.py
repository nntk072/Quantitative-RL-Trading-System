"""Deterministic price-grid discretization for market bars and executable quotes."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from omegaconf import OmegaConf

ROUNDING_MODE = "nearest_half_away_from_zero"


def configured_price_grid_increment(cfg: Any) -> float | None:
    """Return the active data price grid, or ``None`` when discretization is off.

    Args:
        cfg: Run configuration used by this operation.

    Returns:
        Result of return the active data price grid, or ``None`` when discretization is off.
    """
    grid = OmegaConf.select(cfg, "data.price_discretization")
    if not grid or not bool(grid.get("enabled", False)):
        return None
    rounding = str(grid.get("rounding", ROUNDING_MODE))
    if rounding != ROUNDING_MODE:
        raise ValueError(f"unsupported price-grid rounding mode: {rounding!r}")
    increment = float(grid.get("increment", 0.0))
    if not np.isfinite(increment) or increment <= 0.0:
        raise ValueError("enabled price discretization requires a finite positive increment")
    return increment


def quantize_prices(values: Any, increment: float) -> np.ndarray[Any, np.dtype[np.float64]]:
    """Round prices to the nearest grid point with deterministic half-away ties.

    For example, with a 0.25 grid, 25633.68 becomes 25633.75. The operation
    preserves NaN and infinity values so existing data validation can handle
    them at its established boundary.

    Args:
        values: Values to process, in input order.
        increment: Numeric value used for the increment.

    Returns:
        Array returned by ``quantize_prices``.
    """
    step = float(increment)
    if not np.isfinite(step) or step <= 0.0:
        raise ValueError("price-grid increment must be finite and positive")
    prices = np.asarray(values, dtype=np.float64)
    scaled = prices / step
    rounded = np.copysign(np.floor(np.abs(scaled) + 0.5), scaled)
    return np.asarray(rounded * step, dtype=np.float64)


def quantize_bar_prices(bars: pd.DataFrame, increment: float | None) -> pd.DataFrame:
    """Return bars with OHLC prices mapped onto *increment*; metadata is unchanged.

    Args:
        bars: Market bars to process.
        increment: Increment used by the operation described above.

    Returns:
        DataFrame returned by ``quantize_bar_prices``.
    """
    if increment is None:
        return bars
    result = bars.copy()
    for column in ("open", "high", "low", "close"):
        if column not in result.columns:
            raise ValueError(f"bar frame is missing price column {column!r}")
        result[column] = quantize_prices(result[column].to_numpy(), increment)
    return result


def price_grid_identity(increment: float | None) -> str:
    """Stable identity string for source-cache validation.

    Args:
        increment: Increment used by the operation described above.

    Returns:
        Text returned by ``price_grid_identity``.
    """
    if increment is None:
        return "price-grid:none"
    return f"price-grid:{ROUNDING_MODE}:{float(increment):.12g}"


def tick_cache_filename(symbol: str, increment: float | None, cache_version: str) -> str:
    """Cache filename that separates raw and discretized quote books.

    Args:
        symbol: Text or path value identifying the symbol.
        increment: Increment used by the operation described above.
        cache_version: Text or path value identifying the cache version.

    Returns:
        Text returned by ``tick_cache_filename``.
    """
    grid = f"{float(increment):.12g}".replace(".", "p") if increment is not None else ""
    suffix = "" if increment is None else f"_grid_{ROUNDING_MODE}_{grid}"
    return f"{symbol}_ticks_{cache_version}{suffix}.parquet"
