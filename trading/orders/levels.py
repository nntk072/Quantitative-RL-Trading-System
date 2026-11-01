from __future__ import annotations

import numpy as np

DEVIATION_KS: tuple[float, ...] = (-1.0, 0.0, 1.0, 1.5, 2.0, 2.25, 2.5, 3.0, 3.5, 4.0, 8.0)


def level_near_candles(
    price: float, candle_lo: float, candle_hi: float, pad_frac: float = 0.5
) -> bool:
    """Return whether a price level is within a padded candle range.

    Args:
        price: Price level being tested.
        candle_lo: Candle low.
        candle_hi: Candle high.
        pad_frac: Padding as a fraction of candle height.

    Returns:
        True when the level is inside the padded range.
    """
    if not np.isfinite(price) or not np.isfinite(candle_lo) or not np.isfinite(candle_hi):
        return False
    span = max(float(candle_hi) - float(candle_lo), 1e-6)
    pad = pad_frac * span
    return float(candle_lo) - pad <= float(price) <= float(candle_hi) + pad


def deviation_levels(
    swing_low: float, swing_high: float, candle_lo: float, candle_hi: float
) -> list[tuple[float, float]]:
    """Find projected levels extended from the latest candle around a swing range.

    Args:
        swing_low: Low endpoint of the measured swing.
        swing_high: High endpoint of the measured swing.
        candle_lo: Low of the candle used for proximity checks.
        candle_hi: High of the candle used for proximity checks.

    Returns:
        Eligible projected prices in configured order.
    """
    if not np.isfinite(swing_low) or not np.isfinite(swing_high):
        return []
    span = float(swing_high) - float(swing_low)
    if span <= 0.0:
        return []
    out: list[tuple[float, float]] = []
    for k in DEVIATION_KS:
        price = float(swing_low) + float(k) * span
        if level_near_candles(price, candle_lo, candle_hi):
            out.append((float(k), price))
    return out
