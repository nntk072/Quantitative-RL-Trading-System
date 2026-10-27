"""Causal Fibonacci-like swing retracement context on one timeframe."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from features.technical.structure import structure_levels

RETRACEMENT_LOW = 0.5
RETRACEMENT_HIGH = 0.786
SWING_LEVELS = (
    1.0,
    0.786,
    0.707,
    0.5,
    0.0,
    -0.5,
    -1.0,
    -1.5,
    -2.0,
    -2.25,
    -2.5,
    -3.0,
    -4.0,
    -6.0,
    -8.0,
)


def level_token(value: float) -> str:
    """Stable column-name token for a configured ladder level."""
    return f"{value:g}".replace("-", "neg_").replace(".", "_")


def build_swing_retracement_features(
    bars: pd.DataFrame,
    *,
    swing_period: int = 5,
    atr_mult: float = 0.0,
    retracement_low: float = RETRACEMENT_LOW,
    retracement_high: float = RETRACEMENT_HIGH,
    level_values: tuple[float, ...] = SWING_LEVELS,
) -> pd.DataFrame:
    """Mark pullbacks into a fib-like retracement band of the latest confirmed leg.

    An up leg (latest confirmed pivot is a swing high) creates a long context
    when price retraces 0.5–0.786 of that leg. Level 1 is the swing-low origin
    and level 0 is the swing-high end. A down leg mirrors the rule for shorts:
    level 1 is the swing-high origin and level 0 is the swing-low end. This is
    a named research entry idea, not a statistical sigma band. The direction
    feature is +1 for a valid up leg, -1 for a valid down leg, and 0 when the
    leg is invalid or unavailable.
    """
    if swing_period < 1:
        raise ValueError("swing_period must be positive")
    if not np.isfinite(atr_mult) or atr_mult < 0.0:
        raise ValueError("atr_mult must be finite and nonnegative")
    if (
        not np.isfinite(retracement_low)
        or not np.isfinite(retracement_high)
        or not 0.0 <= retracement_low < retracement_high <= 1.0
    ):
        raise ValueError("retracement bounds must satisfy 0 <= low < high <= 1")
    missing = {"high", "low", "close"}.difference(bars.columns)
    if missing:
        raise ValueError(f"swing-retracement bars missing columns: {sorted(missing)}")

    structure = structure_levels(bars, swing_period=swing_period, atr_mult=atr_mult)
    swing_high = pd.to_numeric(structure["last_swing_high"], errors="coerce")
    swing_low = pd.to_numeric(structure["last_swing_low"], errors="coerce")
    high_time = pd.to_datetime(structure["last_swing_high_time"], errors="coerce")
    low_time = pd.to_datetime(structure["last_swing_low_time"], errors="coerce")
    close = pd.to_numeric(bars["close"], errors="coerce")
    if not level_values or any(not np.isfinite(value) for value in level_values):
        raise ValueError("swing levels must be a nonempty sequence of finite values")
    if len(set(level_values)) != len(level_values):
        raise ValueError("swing levels must not contain duplicates")
    span = swing_high - swing_low
    leg_start_time = high_time.where(high_time.lt(low_time), low_time)
    leg_end_time = high_time.where(high_time.gt(low_time), low_time)
    valid = (
        swing_high.notna()
        & swing_low.notna()
        & high_time.notna()
        & low_time.notna()
        & span.gt(0.0)
        & close.notna()
    )
    up_leg = valid & high_time.gt(low_time)
    down_leg = valid & low_time.gt(high_time)
    long_retrace = (swing_high - close) / span
    short_retrace = (close - swing_low) / span
    # A confirmed impulse remains usable only while its body close stays
    # between level 0 and the configured deep-retracement boundary. Latch an
    # invalidated leg off until a different confirmed pivot pair appears.
    setup_valid = np.zeros(len(bars), dtype=bool)
    active_leg: tuple[int, int, int] | None = None
    leg_is_valid = False
    start_ns = np.asarray(leg_start_time, dtype="datetime64[ns]").view(np.int64)
    end_ns = np.asarray(leg_end_time, dtype="datetime64[ns]").view(np.int64)
    for i in range(len(bars)):
        if not valid.iloc[i]:
            active_leg = None
            leg_is_valid = False
            continue
        leg_direction = 1 if up_leg.iloc[i] else -1 if down_leg.iloc[i] else 0
        leg_key = (int(start_ns[i]), int(end_ns[i]), leg_direction)
        if leg_key != active_leg:
            active_leg = leg_key
            leg_is_valid = leg_direction != 0
        if leg_is_valid:
            retracement = long_retrace.iloc[i] if leg_direction == 1 else short_retrace.iloc[i]
            if not 0.0 <= retracement <= retracement_high:
                leg_is_valid = False
        setup_valid[i] = leg_is_valid
    valid_setup = pd.Series(setup_valid, index=bars.index)
    long_active = valid_setup & up_leg & long_retrace.between(retracement_low, retracement_high)
    short_active = valid_setup & down_leg & short_retrace.between(retracement_low, retracement_high)
    band_low = swing_high - retracement_high * span
    band_high = swing_high - retracement_low * span
    short_band_low = swing_low + retracement_low * span
    short_band_high = swing_low + retracement_high * span
    # Level 0 is the end of the impulse; level 1 is its origin. Negative
    # levels project beyond the impulse end. The same coordinate is mirrored
    # for a down leg. Store raw prices for charting and range-normalized
    # distances for the policy; raw prices are excluded by the observation
    # schema.
    level_prices: dict[str, NDArray[np.float64]] = {}
    level_distances: dict[str, NDArray[np.float64]] = {}
    for level in level_values:
        token = level_token(float(level))
        price = np.where(
            up_leg,
            swing_high - float(level) * span,
            np.where(down_leg, swing_low + float(level) * span, np.nan),
        )
        level_prices[f"standard_deviation_level_{token}_price"] = np.where(
            setup_valid,
            price,
            np.nan,
        )
        level_distances[f"standard_deviation_level_{token}_distance"] = np.where(
            setup_valid,
            (price - close) / span,
            np.nan,
        )

    leg_start_time_ns = (
        pd.DatetimeIndex(leg_start_time).to_numpy(dtype="datetime64[ns]").astype(np.int64)
    )
    leg_end_time_ns = (
        pd.DatetimeIndex(leg_end_time).to_numpy(dtype="datetime64[ns]").astype(np.int64)
    )
    result = pd.DataFrame(
        {
            "standard_deviation_entry_long": long_active.astype("float64"),
            "standard_deviation_entry_short": short_active.astype("float64"),
            "standard_deviation_leg_valid": setup_valid.astype("float64"),
            "standard_deviation_leg_direction": np.where(
                setup_valid, np.where(up_leg, 1.0, -1.0), 0.0
            ),
            "standard_deviation_retracement_fraction": np.where(
                up_leg, long_retrace, np.where(down_leg, short_retrace, np.nan)
            ),
            "standard_deviation_band_low": np.where(
                setup_valid,
                np.where(up_leg, band_low, np.where(down_leg, short_band_low, np.nan)),
                np.nan,
            ),
            "standard_deviation_band_high": np.where(
                setup_valid,
                np.where(up_leg, band_high, np.where(down_leg, short_band_high, np.nan)),
                np.nan,
            ),
            "standard_deviation_leg_start_time_ns": np.where(
                setup_valid, leg_start_time_ns, np.nan
            ),
            "standard_deviation_leg_end_time_ns": np.where(setup_valid, leg_end_time_ns, np.nan),
        },
        index=bars.index,
    )
    return pd.concat(
        [
            result,
            pd.DataFrame(level_prices, index=bars.index),
            pd.DataFrame(level_distances, index=bars.index),
        ],
        axis=1,
    )


__all__ = [
    "RETRACEMENT_HIGH",
    "RETRACEMENT_LOW",
    "SWING_LEVELS",
    "build_swing_retracement_features",
    "level_token",
]
