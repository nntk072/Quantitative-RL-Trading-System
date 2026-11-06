"""Price and expiry rules for policy-selected entry orders."""

from __future__ import annotations

import math

import pandas as pd


def limit_price_from_atr_offset(
    *,
    direction: int,
    reference_price: float,
    atr: float,
    offset_atr: float,
    point_size: float,
) -> float:
    """Place a passive limit from the decision close and round by trade side.

    Long limits are rounded down to the price grid; short limits are rounded
    up. The decision close is a causal reference, while the eventual fill must
    still be established by executable quote data.

    Args:
        direction: Trade direction, ``1`` for long or ``-1`` for short.
        reference_price: Causal close price used to place the order.
        atr: Current average true range in price units.
        offset_atr: Distance from the reference price, measured in ATR units.
        point_size: Minimum tradable price increment.

    Returns:
        Passive limit price rounded to the instrument's price grid.
    """
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or +1")
    values = (reference_price, atr, offset_atr, point_size)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("limit price inputs must be finite")
    if reference_price <= 0.0 or atr <= 0.0 or offset_atr < 0.0 or point_size <= 0.0:
        raise ValueError(
            "reference price, ATR, and point size must be positive; offset nonnegative"
        )
    raw_price = float(reference_price) - direction * float(atr) * float(offset_atr)
    if raw_price <= 0.0:
        raise ValueError("limit price must remain positive")
    ticks = raw_price / float(point_size)
    rounded_ticks = math.floor(ticks + 1e-12) if direction == 1 else math.ceil(ticks - 1e-12)
    return float(rounded_ticks * float(point_size))


def limit_order_expiry(
    submission_time: pd.Timestamp,
    ttl_bars: int,
    bar_duration: pd.Timedelta,
) -> pd.Timestamp:
    """Return the inclusive expiry timestamp for an M1-bar TTL.

    Args:
        submission_time: Time the limit order became active.
        ttl_bars: Number of bar durations for which the order remains valid.
        bar_duration: Duration represented by one TTL bar.

    Returns:
        Time at which the order's final eligible bar expires.
    """
    if isinstance(ttl_bars, bool) or ttl_bars < 1 or int(ttl_bars) != ttl_bars:
        raise ValueError("ttl_bars must be a positive integer")
    if not isinstance(bar_duration, pd.Timedelta) or bar_duration <= pd.Timedelta(0):
        raise ValueError("bar_duration must be a positive pandas Timedelta")
    submitted = pd.Timestamp(submission_time)
    if submitted.tz is None:
        raise ValueError("submission_time must be timezone-aware")
    return submitted + int(ttl_bars) * bar_duration


__all__ = ["limit_order_expiry", "limit_price_from_atr_offset"]
