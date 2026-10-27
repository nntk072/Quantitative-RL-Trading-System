"""Causal, context-qualified order-block zones.

This operational definition records the last opposing candle before an ATR-sized
displacement closes through a previously confirmed swing. It is a reproducible
feature definition, not evidence that the pattern has predictive value. It is
independent of PO3: no PO3 phase, sweep, or IFVG confirmation is required.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from features.technical.indicators import atr
from features.technical.structure import structure_levels


def build_order_block_features(
    bars: pd.DataFrame,
    *,
    swing_period: int = 5,
    impulse_atr: float = 0.5,
    search_bars: int = 10,
    max_age_bars: int = 240,
    atr_period: int = 14,
) -> pd.DataFrame:
    """Return active bullish/bearish OB zones, retests, ages, and ATR distances.

    A bullish block is the last bearish candle in the configured lookback
    before a bullish displacement closes above the prior confirmed swing high.
    A bearish block mirrors that rule. The zone becomes observable at the
    displacement bar close. Later bars may signal a zone retest. Close-through
    of the distal edge or expiry deactivates the zone.
    """
    if swing_period < 1 or search_bars < 1 or max_age_bars < 1:
        raise ValueError("order-block periods and age must be positive")
    if not np.isfinite(impulse_atr) or impulse_atr < 0.0:
        raise ValueError("impulse_atr must be finite and nonnegative")
    required = {"open", "high", "low", "close"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"order-block bars missing columns: {sorted(missing)}")

    n = len(bars)
    opens = bars["open"].to_numpy(dtype=float)
    highs = bars["high"].to_numpy(dtype=float)
    lows = bars["low"].to_numpy(dtype=float)
    closes = bars["close"].to_numpy(dtype=float)
    atr_values = atr(bars, period=atr_period).to_numpy(dtype=float)
    levels = structure_levels(bars, swing_period=swing_period)
    prior_high = levels["last_swing_high"].shift(1).to_numpy(dtype=float)
    prior_low = levels["last_swing_low"].shift(1).to_numpy(dtype=float)

    columns = {
        "ob_bull_active": np.zeros(n),
        "ob_bull_retest": np.zeros(n),
        "ob_bull_low": np.full(n, np.nan),
        "ob_bull_high": np.full(n, np.nan),
        "ob_bull_mid": np.full(n, np.nan),
        "ob_bull_origin_time_ms": np.full(n, np.nan),
        "ob_bull_age": np.full(n, np.nan),
        "ob_bull_distance_atr": np.full(n, np.nan),
        "ob_bull_new": np.zeros(n),
        "ob_bear_active": np.zeros(n),
        "ob_bear_retest": np.zeros(n),
        "ob_bear_low": np.full(n, np.nan),
        "ob_bear_high": np.full(n, np.nan),
        "ob_bear_mid": np.full(n, np.nan),
        "ob_bear_origin_time_ms": np.full(n, np.nan),
        "ob_bear_age": np.full(n, np.nan),
        "ob_bear_distance_atr": np.full(n, np.nan),
        "ob_bear_new": np.zeros(n),
    }
    zones: dict[str, tuple[float, float, int, int] | None] = {"bull": None, "bear": None}
    pending_retests: dict[str, tuple[int, float] | None] = {"bull": None, "bear": None}
    times_ms = (
        pd.DatetimeIndex(bars.index).to_numpy(dtype="datetime64[ns]").view(np.int64) // 1_000_000
    )

    for i in range(n):
        atr_now = atr_values[i]
        bullish_break = (
            np.isfinite(prior_high[i])
            and closes[i] > prior_high[i]
            and np.isfinite(atr_now)
            and closes[i] - opens[i] >= impulse_atr * atr_now
        )
        bearish_break = (
            np.isfinite(prior_low[i])
            and closes[i] < prior_low[i]
            and np.isfinite(atr_now)
            and opens[i] - closes[i] >= impulse_atr * atr_now
        )
        if bullish_break:
            for j in range(i - 1, max(-1, i - search_bars - 1), -1):
                if closes[j] < opens[j]:
                    zones["bull"] = (float(lows[j]), float(highs[j]), i, j)
                    pending_retests["bull"] = None
                    columns["ob_bull_new"][i] = 1.0
                    break
        if bearish_break:
            for j in range(i - 1, max(-1, i - search_bars - 1), -1):
                if closes[j] > opens[j]:
                    zones["bear"] = (float(lows[j]), float(highs[j]), i, j)
                    pending_retests["bear"] = None
                    columns["ob_bear_new"][i] = 1.0
                    break

        for side in ("bull", "bear"):
            zone = zones[side]
            if zone is None:
                continue
            zone_low, zone_high, created_at, origin_at = zone
            age = i - created_at
            invalidated = closes[i] < zone_low if side == "bull" else closes[i] > zone_high
            if age > max_age_bars or invalidated:
                zones[side] = None
                pending_retests[side] = None
                continue
            active = f"ob_{side}_active"
            columns[active][i] = 1.0
            columns[f"ob_{side}_low"][i] = zone_low
            columns[f"ob_{side}_high"][i] = zone_high
            columns[f"ob_{side}_mid"][i] = 0.5 * (zone_low + zone_high)
            columns[f"ob_{side}_origin_time_ms"][i] = float(times_ms[origin_at])
            columns[f"ob_{side}_age"][i] = float(age)
            if np.isfinite(atr_now) and atr_now > 0.0:
                if closes[i] > zone_high:
                    distance = closes[i] - zone_high
                elif closes[i] < zone_low:
                    distance = closes[i] - zone_low
                else:
                    distance = 0.0
                columns[f"ob_{side}_distance_atr"][i] = distance / atr_now
            pending = pending_retests[side]
            if pending is not None and i > pending[0]:
                confirms = closes[i] > pending[1] if side == "bull" else closes[i] < pending[1]
                if confirms:
                    columns[f"ob_{side}_retest"][i] = 1.0
                    pending_retests[side] = None
            if age > 0 and lows[i] <= zone_high and highs[i] >= zone_low:
                pending_retests[side] = (i, highs[i] if side == "bull" else lows[i])

    return pd.DataFrame(columns, index=bars.index)


__all__ = ["build_order_block_features"]
