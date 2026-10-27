"""SMT (Smart Money Technique) divergence between US500 and US100."""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from features.technical.swings import detect_pivots


def smt_divergence(
    primary: pd.DataFrame,
    secondary: pd.DataFrame,
    swing_period: int = 5,
    corr_window: int = 20,
) -> pd.DataFrame:
    """Compute SMT divergence features.

    Args:
        primary: US100 bar DataFrame (reference instrument).
        secondary: US500 bar DataFrame aligned to primary index.
        swing_period: Bars on each side to detect a confirmed fractal pivot.
        corr_window: Rolling correlation window between closes.

    Returns:
        DataFrame with smt_bearish, smt_bullish, smt_corr, smt_spread.
    """
    sec_close = secondary["close"].reindex(primary.index, method="ffill")
    sec_aligned = secondary.reindex(primary.index, method="ffill")

    pr_piv = detect_pivots(primary, left=swing_period, right=swing_period)
    sec_piv = detect_pivots(sec_aligned, left=swing_period, right=swing_period)

    def _paired_divergences(
        primary_event: pd.Series,
        secondary_event: pd.Series,
        primary_price: pd.Series,
        secondary_price: pd.Series,
        *,
        high: bool,
    ) -> NDArray[np.float64]:
        """Compare consecutive confirmed, time-matched swings without lookahead."""
        p_events = np.flatnonzero(primary_event.to_numpy(dtype=bool))
        s_events = np.flatnonzero(secondary_event.to_numpy(dtype=bool))
        p_prices = primary_price.to_numpy(dtype=float)
        s_prices = secondary_price.to_numpy(dtype=float)
        tolerance = max(1, swing_period)
        pairs: list[tuple[int, float, float]] = []
        used_secondary: set[int] = set()
        for p_i in p_events:
            lo = int(np.searchsorted(s_events, p_i - tolerance, side="left"))
            hi = int(np.searchsorted(s_events, p_i + tolerance, side="right"))
            candidates = [int(s_i) for s_i in s_events[lo:hi] if int(s_i) not in used_secondary]
            if not candidates:
                continue
            s_i = min(candidates, key=lambda i: (abs(i - int(p_i)), i))
            used_secondary.add(s_i)
            event_i = max(int(p_i), s_i)
            pairs.append((event_i, float(p_prices[p_i]), float(s_prices[s_i])))
        result = np.zeros(len(primary_event), dtype=float)
        previous: tuple[float, float] | None = None
        for event_i, p_price, s_price in sorted(pairs):
            if previous is not None:
                p_prev, s_prev = previous
                if high:
                    diverges = (p_price > p_prev and s_price <= s_prev) or (
                        s_price > s_prev and p_price <= p_prev
                    )
                else:
                    diverges = (p_price < p_prev and s_price >= s_prev) or (
                        s_price < s_prev and p_price >= p_prev
                    )
                if diverges:
                    result[event_i] = 1.0
            previous = (p_price, s_price)
        return result

    smt_bearish = _paired_divergences(
        pr_piv["pivot_high_event"],
        sec_piv["pivot_high_event"],
        pr_piv["pivot_high_extreme"],
        sec_piv["pivot_high_extreme"],
        high=True,
    )
    smt_bullish = _paired_divergences(
        pr_piv["pivot_low_event"],
        sec_piv["pivot_low_event"],
        pr_piv["pivot_low_extreme"],
        sec_piv["pivot_low_extreme"],
        high=False,
    )

    smt_corr = primary["close"].rolling(corr_window).corr(sec_close)
    smt_spread = (primary["close"] - sec_close) / primary["close"].replace(0, np.nan)

    return pd.DataFrame(
        {
            "smt_bearish": smt_bearish,
            "smt_bullish": smt_bullish,
            "smt_corr": smt_corr,
            "smt_spread": smt_spread,
        },
        index=primary.index,
    )
